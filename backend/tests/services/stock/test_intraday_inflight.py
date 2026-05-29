import asyncio

import pytest

from app.models.stock import IntradayData, IntradayItem
from app.services.stock import intraday


@pytest.mark.asyncio
async def test_get_intraday_dedupes_concurrent_same_key(monkeypatch):
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

    result_a, result_b = await asyncio.gather(
        intraday.get_intraday("600519"),
        intraday.get_intraday("600519"),
    )

    assert result_a == result_b
    assert calls == 1
    assert len(writes) == 1


@pytest.mark.asyncio
async def test_get_intraday_uses_cache_without_loader(monkeypatch):
    cached = IntradayData(code="600519", prev_close=None, items=[])

    async def fake_load(*args, **kwargs):
        raise AssertionError("loader should not be called")

    monkeypatch.setattr(intraday, "get_last_trade_date", lambda code: "2026-05-25")
    monkeypatch.setattr(intraday, "_load_intraday", fake_load)
    monkeypatch.setattr(intraday.cache, "get", lambda key: cached)
    intraday._intraday_singleflight.clear()

    result = await intraday.get_intraday("600519")

    assert result is cached


@pytest.mark.asyncio
async def test_get_intraday_clears_inflight_after_failure(monkeypatch):
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

    with pytest.raises(RuntimeError, match="temporary failure"):
        await intraday.get_intraday("600519")

    result = await intraday.get_intraday("600519")

    assert result.code == "600519"
    assert calls == 2
