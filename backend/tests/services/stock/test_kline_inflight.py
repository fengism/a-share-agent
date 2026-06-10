import asyncio

from app.models.stock import KlineData, KlineItem
from app.services.stock import kline


def test_get_kline_dedupes_concurrent_same_key(monkeypatch):
    """get_kline coalesces concurrent requests for the same key into one loader call."""
    calls = 0

    async def fake_load(sym, period, start_date, end_date, adjust):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return KlineData(code=sym.raw, period=period, adjust=adjust, items=[KlineItem(code=sym.raw, date="20260525", open=1, close=2, high=3, low=1, volume=100, amount=200)])

    writes = []
    monkeypatch.setattr(kline, "cache_date", lambda: "20260525")
    monkeypatch.setattr(kline, "one_year_ago_date", lambda: "20250525")
    monkeypatch.setattr(kline, "_load_kline", fake_load)
    monkeypatch.setattr(kline.cache, "get", lambda key: None)
    monkeypatch.setattr(kline.cache, "set", lambda *args, **kwargs: writes.append((args, kwargs)))
    kline._kline_singleflight.clear()

    async def run_both():
        return await asyncio.gather(
            kline.get_kline("600519"),
            kline.get_kline("600519"),
        )

    result_a, result_b = asyncio.run(run_both())

    assert result_a == result_b
    assert calls == 1
    assert len(writes) == 1


def test_get_kline_does_not_dedupe_different_keys(monkeypatch):
    """get_kline issues separate loader calls for different stock codes."""
    requested: list[str] = []

    async def fake_load(sym, period, start_date, end_date, adjust):
        requested.append(sym.raw)
        await asyncio.sleep(0.01)
        return KlineData(code=sym.raw, period=period, adjust=adjust, items=[])

    monkeypatch.setattr(kline, "cache_date", lambda: "20260525")
    monkeypatch.setattr(kline, "one_year_ago_date", lambda: "20250525")
    monkeypatch.setattr(kline, "_load_kline", fake_load)
    monkeypatch.setattr(kline.cache, "get", lambda key: None)
    monkeypatch.setattr(kline.cache, "set", lambda *args, **kwargs: None)
    kline._kline_singleflight.clear()

    async def run_both():
        await asyncio.gather(
            kline.get_kline("600519"),
            kline.get_kline("000858"),
        )

    asyncio.run(run_both())

    assert sorted(requested) == ["000858", "600519"]


def test_get_kline_uses_cache_without_loader(monkeypatch):
    """get_kline returns the cached payload without invoking the loader."""
    cached = KlineData(code="600519", period="daily", adjust="qfq", items=[])

    async def fake_load(*args, **kwargs):
        raise AssertionError("loader should not be called")

    monkeypatch.setattr(kline, "cache_date", lambda: "20260525")
    monkeypatch.setattr(kline, "one_year_ago_date", lambda: "20250525")
    monkeypatch.setattr(kline, "_load_kline", fake_load)
    monkeypatch.setattr(kline.cache, "get", lambda key: cached)
    kline._kline_singleflight.clear()

    result = asyncio.run(kline.get_kline("600519"))

    assert result is cached
