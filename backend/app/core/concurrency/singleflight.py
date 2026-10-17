"""合并相同键的并发同步与异步请求。"""

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from concurrent.futures import Future
from functools import partial
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


class SyncSingleFlight(Generic[T]):
    """合并相同键的并发同步请求，让调用方共享同一次加载结果。"""

    def __init__(self) -> None:
        self._inflight: dict[Hashable, Future[T]] = {}
        self._lock = Lock()

    def do(self, key: Hashable, loader: Callable[[], T]) -> T:
        """同步执行 loader，同一时刻相同 key 仅由首个调用方负责加载。"""
        with self._lock:
            future = self._inflight.get(key)
            is_leader = future is None
            if future is None:
                future = Future()
                self._inflight[key] = future

        if not is_leader:
            return future.result()

        try:
            result = loader()
        except BaseException as error:
            future.set_exception(error)
            raise
        else:
            future.set_result(result)
            return result
        finally:
            with self._lock:
                if self._inflight.get(key) is future:
                    self._inflight.pop(key, None)

    def clear(self) -> None:
        """清空正在跟踪的同步请求引用。"""
        with self._lock:
            self._inflight.clear()


class AsyncSingleFlight(Generic[T]):
    """Purpose: 去重同一 key 的并发异步调用，确保同一时刻只有一个 loader 任务在执行。"""

    def __init__(self) -> None:
        """Initialize the single-flight registry with empty inflight map and lock."""
        self._inflight: dict[Hashable, asyncio.Future[T]] = {}
        self._lock = asyncio.Lock()

    def _remove_task(self, key: Hashable, task: asyncio.Future[T]) -> None:
        if self._inflight.get(key) is task:
            self._inflight.pop(key, None)

    def _on_task_done(self, key: Hashable, task: asyncio.Future[T]) -> None:
        if not task.cancelled():
            task.exception()
        self._remove_task(key, task)

    async def do(self, key: Hashable, loader: Callable[[], Awaitable[T]]) -> T:
        """Run loader once per concurrent key, sharing its result with all callers.

        Param:
            key: unique key to dedupe concurrent calls
            loader: async factory that produces the value
        Return:
            the value produced by loader, shared across all callers of the same key
        """
        async with self._lock:
            task = self._inflight.get(key)
            if task is not None and task.done():
                self._remove_task(key, task)
                task = None
            if task is None:
                # ensure_future 同时接受协程与其他 awaitable，比 create_task 更宽泛
                task = asyncio.ensure_future(loader())
                self._inflight[key] = task
                task.add_done_callback(partial(self._on_task_done, key))

        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self._remove_task(key, task)

    def clear(self) -> None:
        """Clear all inflight task references.

        Param:
            None
        Return:
            None
        """
        self._inflight.clear()
