import logging
import time
from collections import OrderedDict
from datetime import datetime
from threading import Lock
from typing import Any

from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class TTLCache:
    """Purpose: 线程安全的带过期时间的内存缓存，支持按 key 读取、写入、删除和清空。"""

    def __init__(self, maxsize: int = 1000, name: str = "ttl_cache") -> None:
        """Initialize the TTL cache with empty store and lock."""
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()
        self._maxsize = maxsize
        self._name = name
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    def get(self, key: str) -> Any | None:
        """Get a cached value by key, returns None if missing or expired.

        Param:
            key: cache key to look up
        Return:
            cached value if present and not expired, otherwise None
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                metrics.record_cache_event(self._name, "miss", size=len(self._store))
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                self._expirations += 1
                metrics.record_cache_event(self._name, "miss", size=len(self._store))
                metrics.record_cache_event(self._name, "expiration", size=len(self._store))
                logger.debug(f"缓存过期: key={key}")
                return None
            # 标记为最近使用（LRU 顺序维护）
            self._store.move_to_end(key)
            self._hits += 1
            metrics.record_cache_event(self._name, "hit", size=len(self._store))
            return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Store a value with a TTL in seconds.

        Param:
            key: cache key
            value: value to store
            ttl: time-to-live in seconds
        Return:
            None
        """
        with self._lock:
            # 达到容量上限时淘汰最久未使用的条目（先淘汰，后插入）
            if key not in self._store and self._maxsize > 0 and len(self._store) >= self._maxsize:
                evicted_key, _ = self._store.popitem(last=False)
                self._evictions += 1
                metrics.record_cache_event(self._name, "eviction", size=len(self._store))
                logger.debug(f"缓存淘汰: key={evicted_key}")
            self._store[key] = (value, time.monotonic() + ttl)
            self._store.move_to_end(key)  # 标记为最近使用
            metrics.record_cache_event(self._name, "set", size=len(self._store))
            logger.debug(f"缓存写入: key={key}, ttl={ttl}s, 当前缓存数={len(self._store)}")

    def delete(self, key: str) -> None:
        """Delete a cached value by key, no-op if missing.

        Param:
            key: cache key to remove
        Return:
            None
        """
        with self._lock:
            self._store.pop(key, None)
            metrics.record_cache_event(self._name, "delete", size=len(self._store))
            logger.debug(f"缓存删除: key={key}")

    def clear(self) -> None:
        """Remove all cached entries.

        Param:
            None
        Return:
            None
        """
        with self._lock:
            count = len(self._store)
            self._store.clear()
            metrics.record_cache_event(self._name, "clear", size=0)
            logger.info(f"缓存清空: 清除{count}条")

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "size": len(self._store),
                "maxsize": self._maxsize,
            }


cache = TTLCache(name="global")


def cache_date() -> str:
    """Return today's date in YYYYMMDD format."""
    return datetime.now().strftime("%Y%m%d")


def dated_cache_key(*parts: object) -> str:
    """Build a cache key with today's date as the final segment."""
    return ":".join(str(part) for part in (*parts, cache_date()))


def dated_cache_key_no_day(*parts: object) -> str:
    """Build a stable cache key without a date segment."""
    return ":".join(str(part) for part in parts)


def one_year_ago_date() -> str:
    """Return the date one year before today in YYYYMMDD format."""
    now = datetime.now()
    try:
        previous_year = now.replace(year=now.year - 1)
    except ValueError:
        previous_year = now.replace(year=now.year - 1, day=28)
    return previous_year.strftime("%Y%m%d")
