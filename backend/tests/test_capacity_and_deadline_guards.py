import pytest

from app.core.cache import TTLCache


class TestTTLCacheCapacity:
    def test_zero_maxsize_is_rejected(self):
        # 旧实现只挡负数，maxsize=0 能通过；但 set() 里所有容量判断都写作
        # `self._maxsize > 0`，于是它既不淘汰也不清过期，静默退化成无界缓存。
        with pytest.raises(ValueError):
            TTLCache(maxsize=0)

    def test_negative_maxsize_is_rejected(self):
        with pytest.raises(ValueError):
            TTLCache(maxsize=-1)

    def test_capacity_is_enforced(self):
        cache = TTLCache(maxsize=3)
        for index in range(10):
            cache.set(f"k{index}", index, 60)
        assert len(cache._store) == 3

    def test_expired_entries_are_purged_before_evicting_live_ones(self):
        cache = TTLCache(maxsize=3)
        cache.set("a", 1, 60)
        cache.set("b", 2, 60)
        cache.set("c", 3, 60)
        # 让全部过期后再写一条：应先清空过期项，而不是逐出仍"活着"的条目
        for key in list(cache._store):
            cache._store[key] = (cache._store[key][0], 0.0)
        cache.set("d", 4, 60)
        assert list(cache._store) == ["d"]
