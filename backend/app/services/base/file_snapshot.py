import asyncio
from pathlib import Path
from typing import Generic, TypeVar

from app.utils.cache import cache

T = TypeVar("T")


class BaseFileSnapshotService(Generic[T]):
    def __init__(self, cache_key: str, ttl: int, file_path: Path):
        self.cache_key = cache_key
        self.ttl = ttl
        self.file_path = file_path
        self.refresh_task: asyncio.Task | None = None

    def get_cached(self) -> T | None:
        return cache.get(self.cache_key)

    def set_cached(self, value: T) -> None:
        cache.set(self.cache_key, value, ttl=self.ttl)

    def should_refresh(self) -> bool:
        return self.refresh_task is None or self.refresh_task.done()

    def start_refresh(self, coro) -> None:
        if self.should_refresh():
            self.refresh_task = asyncio.create_task(coro)

    def clear_refresh_task(self) -> None:
        self.refresh_task = None
