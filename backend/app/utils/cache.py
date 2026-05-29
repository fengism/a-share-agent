import logging
import time
from datetime import datetime
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
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
        with self._lock:
            self._store[key] = (value, time.time() + ttl)
            logger.debug(f"缓存写入: key={key}, ttl={ttl}s, 当前缓存数={len(self._store)}")

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            logger.debug(f"缓存删除: key={key}")

    def clear(self) -> None:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.info(f"缓存清空: 清除{count}条")


def cache_date() -> str:
    return datetime.now().strftime("%Y%m%d")


def dated_cache_key(*parts: object) -> str:
    return ":".join(str(part) for part in (*parts, cache_date()))

def dated_cache_key_no_day(*parts: object) -> str:
    return ":".join(str(part) for part in (*parts,))


def one_year_ago_date() -> str:
    now = datetime.now()
    return now.replace(year=now.year - 1).strftime("%Y%m%d")


cache = TTLCache()
