import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Generic, TypeVar

from app.core.cache import reference_cache as cache

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BaseFileSnapshotService(Generic[T]):
    """Purpose: 基于文件+内存缓存的快照服务基类，提供缓存读写和异步刷新任务调度。"""

    def __init__(self, cache_key: str, ttl: int, file_path: Path):
        """Initialize the snapshot service with cache key, TTL, and file path."""
        self.cache_key = cache_key
        self.ttl = ttl
        self.file_path = file_path
        self.refresh_task: asyncio.Task[None] | None = None

    def get_cached(self) -> T | None:
        """Get the cached snapshot value, returns None if missing or expired.

        Param:
            None
        Return:
            cached value or None
        """
        return cache.get(self.cache_key)

    def set_cached(self, value: T) -> None:
        """Store a snapshot value in the cache with the configured TTL.

        Param:
            value: value to cache
        Return:
            None
        """
        cache.set(self.cache_key, value, ttl=self.ttl)

    def should_refresh(self) -> bool:
        """Check whether a refresh task can be started.

        Param:
            None
        Return:
            True if there is no running refresh task
        """
        return self.refresh_task is None or self.refresh_task.done()

    def start_refresh(self, factory: Callable[[], Awaitable[None]]) -> bool:
        """Start an async refresh task if no task is currently running.

        Param:
            factory: callback that creates the refresh coroutine on demand
        Return:
            True if a new task was started, otherwise False
        """
        if not self.should_refresh():
            return False
        task = asyncio.create_task(
            factory(),
            name=f"{self.cache_key}_refresh",
        )
        self.refresh_task = task
        task.add_done_callback(self._on_refresh_done)
        return True

    def _on_refresh_done(self, task: asyncio.Task[None]) -> None:
        if self.refresh_task is task:
            self.refresh_task = None
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "文件快照后台刷新失败: cache_key=%s task=%s",
                self.cache_key,
                task.get_name(),
                exc_info=(type(error), error, error.__traceback__),
            )

    def clear_refresh_task(self) -> None:
        """Clear the reference to the current refresh task.

        Param:
            None
        Return:
            None
        """
        self.refresh_task = None
