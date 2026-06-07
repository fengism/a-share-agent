import logging
import time
from datetime import datetime
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    """Purpose: 线程安全的带过期时间的内存缓存，支持按 key 读取、写入、删除和清空。"""

    def __init__(self) -> None:
        """Initialize the TTL cache with empty store and lock."""
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

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
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                logger.debug(f"缓存过期: key={key}")
                return None
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
            self._store[key] = (value, time.time() + ttl)
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
            logger.info(f"缓存清空: 清除{count}条")


def cache_date() -> str:
    """Return today's date string in YYYYMMDD format.

    Param:
        None
    Return:
        today's date formatted as "YYYYMMDD"
    """
    return datetime.now().strftime("%Y%m%d")


def dated_cache_key(*parts: object) -> str:
    """Build a cache key that includes today's date as the last segment.

    Param:
        parts: variable key segments to join with ":"
    Return:
        colon-joined cache key with today's date appended
    """
    return ":".join(str(part) for part in (*parts, cache_date()))

def dated_cache_key_no_day(*parts: object) -> str:
    """Build a cache key without the date segment.

    Param:
        parts: variable key segments to join with ":"
    Return:
        colon-joined cache key without date
    """
    return ":".join(str(part) for part in (*parts,))


def one_year_ago_date() -> str:
    """Return the date one year before today in YYYYMMDD format.

    Param:
        None
    Return:
        date one year ago formatted as "YYYYMMDD"
    """
    now = datetime.now()
    return now.replace(year=now.year - 1).strftime("%Y%m%d")


cache = TTLCache()
