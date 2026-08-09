from __future__ import annotations

from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Generic, Hashable, TypeVar

ResourceT = TypeVar("ResourceT")


@dataclass
class _Entry(Generic[ResourceT]):
    resource: ResourceT
    active_leases: int = 0


class SyncResourcePool(Generic[ResourceT]):
    """线程安全的引用计数 LRU 资源池，只淘汰空闲资源。"""

    def __init__(self, maxsize: int, close: Callable[[ResourceT], None]):
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._maxsize = maxsize
        self._close = close
        self._entries: OrderedDict[Hashable, _Entry[ResourceT]] = OrderedDict()
        self._lock = Lock()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    @contextmanager
    def borrow(self, key: Hashable, factory: Callable[[], ResourceT]) -> Iterator[ResourceT]:
        entry, evicted = self._acquire(key, factory)
        self._close_many(evicted)
        try:
            yield entry.resource
        finally:
            self._close_many(self._release(key, entry))

    def close_all(self) -> None:
        with self._lock:
            resources = [entry.resource for entry in self._entries.values()]
            self._entries.clear()
        self._close_many(resources)

    def _acquire(
        self,
        key: Hashable,
        factory: Callable[[], ResourceT],
    ) -> tuple[_Entry[ResourceT], list[ResourceT]]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(factory())
                self._entries[key] = entry
            entry.active_leases += 1
            self._entries.move_to_end(key)
            evicted = self._collect_evictions_locked()
        return entry, evicted

    def _release(self, key: Hashable, entry: _Entry[ResourceT]) -> list[ResourceT]:
        with self._lock:
            current = self._entries.get(key)
            if current is entry:
                entry.active_leases = max(0, entry.active_leases - 1)
            return self._collect_evictions_locked()

    def _collect_evictions_locked(self) -> list[ResourceT]:
        evicted: list[ResourceT] = []
        while len(self._entries) > self._maxsize:
            victim_key = next(
                (key for key, entry in self._entries.items() if entry.active_leases == 0),
                None,
            )
            if victim_key is None:
                break
            evicted.append(self._entries.pop(victim_key).resource)
        return evicted

    def _close_many(self, resources: list[ResourceT]) -> None:
        for resource in resources:
            self._close(resource)


class AsyncResourcePool(Generic[ResourceT]):
    """支持异步关闭资源的引用计数 LRU 池。"""

    def __init__(self, maxsize: int, close: Callable[[ResourceT], Awaitable[None]]):
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._maxsize = maxsize
        self._close = close
        self._entries: OrderedDict[Hashable, _Entry[ResourceT]] = OrderedDict()
        self._lock = Lock()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    @asynccontextmanager
    async def borrow(self, key: Hashable, factory: Callable[[], ResourceT]) -> AsyncIterator[ResourceT]:
        entry, evicted = self._acquire(key, factory)
        await self._close_many(evicted)
        try:
            yield entry.resource
        finally:
            await self._close_many(self._release(key, entry))

    async def close_all(self) -> None:
        with self._lock:
            resources = [entry.resource for entry in self._entries.values()]
            self._entries.clear()
        await self._close_many(resources)

    def _acquire(
        self,
        key: Hashable,
        factory: Callable[[], ResourceT],
    ) -> tuple[_Entry[ResourceT], list[ResourceT]]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(factory())
                self._entries[key] = entry
            entry.active_leases += 1
            self._entries.move_to_end(key)
            evicted = self._collect_evictions_locked()
        return entry, evicted

    def _release(self, key: Hashable, entry: _Entry[ResourceT]) -> list[ResourceT]:
        with self._lock:
            current = self._entries.get(key)
            if current is entry:
                entry.active_leases = max(0, entry.active_leases - 1)
            return self._collect_evictions_locked()

    def _collect_evictions_locked(self) -> list[ResourceT]:
        evicted: list[ResourceT] = []
        while len(self._entries) > self._maxsize:
            victim_key = next(
                (key for key, entry in self._entries.items() if entry.active_leases == 0),
                None,
            )
            if victim_key is None:
                break
            evicted.append(self._entries.pop(victim_key).resource)
        return evicted

    async def _close_many(self, resources: list[ResourceT]) -> None:
        for resource in resources:
            await self._close(resource)
