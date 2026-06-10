import asyncio

from app.models.stock import IntradayData, IntradayItem
from app.services.stock import intraday


def test_get_intraday_dedupes_concurrent_same_key(monkeypatch):
    """get_intraday coalesces concurrent requests for the same symbol into one loader call."""
    calls = 0

    async def fake_load(sym, date):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return IntradayData(code=sym.raw, prev_close=10.0, items=[IntradayItem(time="09:30", price=10.1)])

    writes = []
    monkeypatch.setattr(intraday, "get_last_trade_date", lambda code: "2026-05-25")
    monkeypatch.setattr(intraday, "_load_intraday", fake_load)
    monkeypatch.setattr(intraday.cache, "get", lambda key: None)
    monkeypatch.setattr(intraday.cache, "set", lambda *args, **kwargs: writes.append((args, kwargs)))
    intraday._intraday_singleflight.clear()

    async def run_both():
        return await asyncio.gather(
            intraday.get_intraday("600519"),
            intraday.get_intraday("600519"),
        )

    result_a, result_b = asyncio.run(run_both())

    assert result_a == result_b
    assert calls == 1
    assert len(writes) == 1


def test_get_intraday_uses_cache_without_loader(monkeypatch):
    """get_intraday returns the cached payload without invoking the loader."""
    cached = IntradayData(code="600519", prev_close=None, items=[])

    async def fake_load(*args, **kwargs):
        raise AssertionError("loader should not be called")

    monkeypatch.setattr(intraday, "get_last_trade_date", lambda code: "2026-05-25")
    monkeypatch.setattr(intraday, "_load_intraday", fake_load)
    monkeypatch.setattr(intraday.cache, "get", lambda key: cached)
    intraday._intraday_singleflight.clear()

    result = asyncio.run(intraday.get_intraday("600519"))

    assert result is cached


def test_get_intraday_clears_inflight_after_failure(monkeypatch):
    """get_intraday clears inflight state and retries after a loader failure."""
    calls = 0

    async def fake_load(sym, date):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return IntradayData(code=sym.raw, prev_close=None, items=[])

    monkeypatch.setattr(intraday, "get_last_trade_date", lambda code: "2026-05-25")
    monkeypatch.setattr(intraday, "_load_intraday", fake_load)
    monkeypatch.setattr(intraday.cache, "get", lambda key: None)
    monkeypatch.setattr(intraday.cache, "set", lambda *args, **kwargs: None)
    intraday._intraday_singleflight.clear()

    async def first_attempt():
        await intraday.get_intraday("600519")

    try:
        asyncio.run(first_attempt())
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "temporary failure" in str(exc)

    result = asyncio.run(intraday.get_intraday("600519"))

    assert result.code == "600519"
    assert calls == 2
