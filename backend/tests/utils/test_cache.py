"""单元测试：TTLCache 和 dated_cache_key。"""
import time
import threading
from app.utils.cache import TTLCache, dated_cache_key, cache_date


def test_cache_basic_set_get():
    c = TTLCache()
    c.set("foo", "bar", ttl=60)
    assert c.get("foo") == "bar"


def test_cache_expiration():
    c = TTLCache()
    c.set("foo", "bar", ttl=1)
    time.sleep(1.1)
    assert c.get("foo") is None


def test_cache_missing_key():
    c = TTLCache()
    assert c.get("nonexistent") is None


def test_cache_delete():
    c = TTLCache()
    c.set("foo", "bar", ttl=60)
    c.delete("foo")
    assert c.get("foo") is None


def test_cache_clear():
    c = TTLCache()
    c.set("a", 1, ttl=60)
    c.set("b", 2, ttl=60)
    c.clear()
    assert c.get("a") is None
    assert c.get("b") is None


def test_cache_thread_safety():
    """验证并发写入不丢失数据。"""
    c = TTLCache()
    errors = []

    def writer(key):
        for i in range(100):
            c.set(key, i, ttl=60)
        try:
            val = c.get(key)
            assert val is not None
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(f"k{n}",)) for n in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(errors) == 0


def test_dated_cache_key():
    today = cache_date()
    key = dated_cache_key("test", "param1", 42)
    assert key == f"test:param1:42:{today}"


def test_cache_int_value():
    c = TTLCache()
    c.set("int_key", 999, ttl=60)
    assert c.get("int_key") == 999


def test_cache_none_value():
    """None 值不应该被缓存当作 'missing'。"""
    c = TTLCache()
    c.set("none_val", None, ttl=60)
    assert c.get("none_val") is None
