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


_Cleanup = Callable[[], Awaitable[None]]


class ManagedEventStream(Generic[EventT]):
    """对外暴露的流对象：**关闭即清理**，无论有没有被迭代过。

    裸 async generator 的 ``finally`` 只在生成器真正开始执行后才会运行。若调用方拿到流
    就关闭或丢弃（客户端在首帧之前断开就是这种情况），``finally`` 不会执行，后台任务
    会在无消费者的情况下继续跑——对一次 LLM/抓取任务来说是白烧额度与数据源配额。

    因此这里用一层薄包装，把 ``aclose()`` 显式映射到「注销 + 取消后台任务」。
    """

    __slots__ = ("_generator", "_cleanup", "_closed")

    def __init__(self, generator: AsyncGenerator[dict, None], cleanup: _Cleanup) -> None:
        self._generator = generator
        self._cleanup = cleanup
        self._closed = False

    def __aiter__(self) -> "ManagedEventStream[EventT]":
        return self

    async def __anext__(self) -> dict:
        return await self._generator.__anext__()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._generator.aclose()
        finally:
            await self._cleanup()


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
    ) -> ManagedEventStream[EventT]:
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

        async def cleanup() -> None:
            await self._unregister(key, task)
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

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
                await cleanup()

        return ManagedEventStream(event_generator(), cleanup)

__all__ = ["KeyedTaskEventStream", "ManagedEventStream"]
