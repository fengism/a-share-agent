"""按业务键管理后台任务并输出 SSE 事件流。"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator, Awaitable, Callable, Hashable
from typing import Any, Generic, Protocol, TypeVar


class SerializableStreamEvent(Protocol):
    type: str

    def model_dump(self) -> dict[str, Any]: ...


EventT = TypeVar("EventT", bound=SerializableStreamEvent)
ProgressCallback = Callable[[EventT], Awaitable[None]]
TaskRunner = Callable[[ProgressCallback[EventT]], Awaitable[None]]


class KeyedTaskEventStream(Generic[EventT]):
    """防止同一业务键重复执行，并统一处理事件、心跳和取消。"""

    def __init__(
        self,
        duplicate_error_factory: Callable[[], Exception],
        *,
        keepalive_seconds: float = 15.0,
    ) -> None:
        self.active_tasks: dict[Hashable, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._duplicate_error_factory = duplicate_error_factory
        self._keepalive_seconds = keepalive_seconds

    async def _register(self, key: Hashable, task: asyncio.Task[None]) -> None:
        async with self._lock:
            existing = self.active_tasks.get(key)
            if existing is not None and not existing.done():
                raise self._duplicate_error_factory()
            self.active_tasks[key] = task

    async def _unregister(self, key: Hashable, task: asyncio.Task[None]) -> None:
        async with self._lock:
            if self.active_tasks.get(key) is task:
                self.active_tasks.pop(key, None)

    async def create(
        self,
        key: Hashable,
        runner: TaskRunner[EventT],
        *,
        error_handler: Callable[[Exception], None] | None = None,
    ) -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue[EventT | None] = asyncio.Queue()

        async def progress_callback(event: EventT) -> None:
            await queue.put(event)

        async def run_and_cleanup() -> None:
            try:
                await runner(progress_callback)
            except Exception as error:
                if error_handler is not None:
                    error_handler(error)
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_and_cleanup())
        try:
            await self._register(key, task)
        except Exception:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            raise

        async def event_generator() -> AsyncGenerator[dict, None]:
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(
                            queue.get(),
                            timeout=self._keepalive_seconds,
                        )
                    except TimeoutError:
                        yield {"comment": "keepalive"}
                        continue

                    if event is None:
                        break
                    yield {
                        "event": event.type,
                        "data": json.dumps(event.model_dump(), ensure_ascii=False, default=str),
                    }
            finally:
                await self._unregister(key, task)
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

        return event_generator()
