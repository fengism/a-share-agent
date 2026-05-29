import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class AsyncSingleFlight(Generic[T]):
    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Task[T]] = {}
        self._lock = asyncio.Lock()

    async def do(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task

        try:
            return await task
        finally:
            if task.done():
                async with self._lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key, None)

    def clear(self) -> None:
        self._inflight.clear()
