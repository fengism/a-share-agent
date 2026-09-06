import logging
import math
import time
from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime
from threading import Lock
from typing import Any

from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class TTLCache:
    """Purpose: 线程安全的带过期时间的内存缓存，支持按 key 读取、写入、删除和清空。"""

    def __init__(self, maxsize: int = 1000, name: str = "ttl_cache") -> None:
        """Initialize the TTL cache with empty store and lock."""
        if maxsize < 0:
            raise ValueError("TTLCache maxsize 不能小于 0")
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()
        self._maxsize = maxsize
        self._name = name
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    def _purge_expired_locked(self, now: float) -> int:
        """Remove expired entries while the caller holds ``_lock``."""
        expired_keys = [
            key for key, (_, expires_at) in self._store.items() if now >= expires_at
        ]
        for key in expired_keys:
            del self._store[key]
            self._expirations += 1
            metrics.record_cache_event(self._name, "expiration", size=len(self._store))
            logger.debug("缓存过期: key=%s", key)
        return len(expired_keys)

    def get_with_status(self, key: str) -> tuple[bool, Any]:
        """Return ``(found, value)`` so a cached ``None`` remains distinguishable."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                metrics.record_cache_event(self._name, "miss", size=len(self._store))
                return False, None
            value, expires_at = entry
            if time.monotonic() >= expires_at:
                del self._store[key]
                self._misses += 1
                self._expirations += 1
                metrics.record_cache_event(self._name, "miss", size=len(self._store))
                metrics.record_cache_event(self._name, "expiration", size=len(self._store))
                logger.debug("缓存过期: key=%s", key)
                return False, None
            self._store.move_to_end(key)
            self._hits += 1
            metrics.record_cache_event(self._name, "hit", size=len(self._store))
            return True, value

    def get(self, key: str) -> Any | None:
        """Get a cached value by key, returns None if missing or expired."""
        return self.get_with_status(key)[1]

    def set(self, key: str, value: Any, ttl: float) -> None:
        """Store a value with a positive, finite TTL in seconds."""
        if not math.isfinite(ttl) or ttl <= 0:
            raise ValueError("TTLCache ttl 必须是大于 0 的有限秒数")
        with self._lock:
            at_capacity = (
                key not in self._store
                and self._maxsize > 0
                and len(self._store) >= self._maxsize
            )
            if at_capacity:
                self._purge_expired_locked(time.monotonic())
            if (
                key not in self._store
                and self._maxsize > 0
                and len(self._store) >= self._maxsize
            ):
                evicted_key, _ = self._store.popitem(last=False)
                self._evictions += 1
                metrics.record_cache_event(self._name, "eviction", size=len(self._store))
                logger.debug("缓存淘汰: key=%s", evicted_key)
            self._store[key] = (value, time.monotonic() + ttl)
            self._store.move_to_end(key)
            metrics.record_cache_event(self._name, "set", size=len(self._store))
            logger.debug("缓存写入: key=%s, ttl=%ss, 当前缓存数=%s", key, ttl, len(self._store))

    def delete(self, key: str) -> None:
        """Delete a cached value by key, no-op if missing."""
        self.delete_many((key,))

    def delete_many(self, keys: Iterable[str]) -> int:
        """Delete several keys atomically and return the number removed."""
        with self._lock:
            removed = 0
            for key in keys:
                if key in self._store:
                    del self._store[key]
                    removed += 1
            metrics.record_cache_event(self._name, "delete", size=len(self._store))
            logger.debug("缓存批量删除: removed=%s", removed)
            return removed

    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys beginning with ``prefix`` and return the number removed."""
        with self._lock:
            matched = [key for key in self._store if key.startswith(prefix)]
            for key in matched:
                del self._store[key]
            metrics.record_cache_event(self._name, "delete", size=len(self._store))
            logger.debug("缓存前缀删除: prefix=%s, removed=%s", prefix, len(matched))
            return len(matched)

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
            # 健康检查应反映当前有效条目，而不是尚未被读取到的过期条目。
            self._purge_expired_locked(time.monotonic())
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "size": len(self._store),
                "maxsize": self._maxsize,
            }


# 保留 legacy/global 实例兼容尚未迁移的调用；主要业务按负载类型使用独立缓存域。
cache = TTLCache(name="global")
market_cache = TTLCache(maxsize=1024, name="market")
reference_cache = TTLCache(maxsize=512, name="reference")
analysis_cache = TTLCache(maxsize=512, name="analysis")

# 高基数、大负载的时序数据（K 线/指数 K 线/分时）使用独立缓存：
# 1) 这类 key 含用户任选的日期区间，键空间无上限，放进全局缓存会持续挤出
#    insights/financials 等低基数热点条目（LRU 互相干扰）；
# 2) 单条体积大（一年日线约 44KB、六年约 264KB），与全局缓存的 1000 条小对象
#    混用时内存不可控。独立 512 条 ≈ 常规一年视图 20MB 量级，最坏情况也可控。
series_cache = TTLCache(maxsize=512, name="series")


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
