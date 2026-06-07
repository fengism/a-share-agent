import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class AsyncSingleFlight(Generic[T]):
    """Purpose: 去重同一 key 的并发异步调用，确保同一时刻只有一个 loader 任务在执行。"""

    def __init__(self) -> None:
        """Initialize the single-flight registry with empty inflight map and lock."""
        self._inflight: dict[str, asyncio.Task[T]] = {}
        self._lock = asyncio.Lock()

    async def do(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        """Run loader once per concurrent key, sharing its result with all callers.

        Param:
            key: unique key to dedupe concurrent calls
            loader: async factory that produces the value
        Return:
            the value produced by loader, shared across all callers of the same key
        """
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
        """Clear all inflight task references.

        Param:
            None
        Return:
            None
        """
        self._inflight.clear()
