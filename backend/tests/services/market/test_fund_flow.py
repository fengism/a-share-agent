import pandas as pd
import pytest

from app.services.market import fund_flow


@pytest.mark.asyncio
async def test_get_hsgt_flow_maps_provider_rows(monkeypatch):
    """get_hsgt_flow converts provider dataframe rows into point dicts with totals."""
    df = pd.DataFrame(
        [
            {"time": "09:30", "hgt_yi": 1.2, "sgt_yi": -0.2},
            {"time": "09:31", "hgt_yi": 1.5, "sgt_yi": 0.5},
        ]
    )

    async def fake_call_blocking(func, *args, **kwargs):
        return df

    monkeypatch.setattr(fund_flow.cache, "get", lambda key: None)
    monkeypatch.setattr(fund_flow.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(fund_flow, "call_blocking", fake_call_blocking)

    result = await fund_flow.get_hsgt_flow()

    assert result["unit"] == "亿元"
    assert result["points"] == [
        {"time": "09:30", "hgt": 1.2, "sgt": -0.2, "total": 1.0},
        {"time": "09:31", "hgt": 1.5, "sgt": 0.5, "total": 2.0},
    ]
    assert result["updated_at"]


@pytest.mark.asyncio
async def test_get_hsgt_flow_skips_rows_without_time(monkeypatch):
    """get_hsgt_flow omits rows whose time field is empty."""
    df = pd.DataFrame(
        [
            {"time": "", "hgt_yi": 1.2, "sgt_yi": 0.3},
            {"time": "09:31", "hgt_yi": None, "sgt_yi": 0.5},
        ]
    )

    async def fake_call_blocking(func, *args, **kwargs):
        return df

    monkeypatch.setattr(fund_flow.cache, "get", lambda key: None)
    monkeypatch.setattr(fund_flow.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(fund_flow, "call_blocking", fake_call_blocking)

    result = await fund_flow.get_hsgt_flow()

    assert result["points"] == [
        {"time": "09:31", "hgt": None, "sgt": 0.5, "total": None},
    ]


@pytest.mark.asyncio
async def test_get_hsgt_flow_skips_nan_time(monkeypatch):
    """get_hsgt_flow omits rows whose time field is NaN/NA."""
    df = pd.DataFrame(
        [
            {"time": pd.NA, "hgt_yi": 1.2, "sgt_yi": 0.3},
            {"time": "09:32", "hgt_yi": 1.0, "sgt_yi": 1.0},
        ]
    )

    async def fake_call_blocking(func, *args, **kwargs):
        return df

    monkeypatch.setattr(fund_flow.cache, "get", lambda key: None)
    monkeypatch.setattr(fund_flow.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(fund_flow, "call_blocking", fake_call_blocking)

    result = await fund_flow.get_hsgt_flow()

    assert result["points"] == [
        {"time": "09:32", "hgt": 1.0, "sgt": 1.0, "total": 2.0},
    ]


@pytest.mark.asyncio
async def test_get_hsgt_flow_uses_cache_without_provider(monkeypatch):
    """get_hsgt_flow returns the cached payload without calling the provider."""
    cached = {"updated_at": "cached", "unit": "亿元", "points": []}

    async def fake_call_blocking(func, *args, **kwargs):
        raise AssertionError("provider should not be called")

    monkeypatch.setattr(fund_flow.cache, "get", lambda key: cached)
    monkeypatch.setattr(fund_flow, "call_blocking", fake_call_blocking)

    result = await fund_flow.get_hsgt_flow()

    assert result == cached


@pytest.mark.asyncio
async def test_get_hsgt_flow_caches_result_for_60_seconds(monkeypatch):
    """get_hsgt_flow stores its result in the cache with a 60-second TTL."""
    df = pd.DataFrame([{"time": "09:30", "hgt_yi": 1.0, "sgt_yi": 2.0}])
    cache_sets = []

    async def fake_call_blocking(func, *args, **kwargs):
        return df

    monkeypatch.setattr(fund_flow.cache, "get", lambda key: None)
    monkeypatch.setattr(fund_flow.cache, "set", lambda *args, **kwargs: cache_sets.append((args, kwargs)))
    monkeypatch.setattr(fund_flow, "call_blocking", fake_call_blocking)

    await fund_flow.get_hsgt_flow()

    assert cache_sets[0][1] == {"ttl": 60}


@pytest.mark.asyncio
async def test_get_hsgt_flow_returns_empty_points_for_empty_dataframe(monkeypatch):
    """get_hsgt_flow returns an empty points list when the provider yields no rows."""
    async def fake_call_blocking(func, *args, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(fund_flow.cache, "get", lambda key: None)
    monkeypatch.setattr(fund_flow.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(fund_flow, "call_blocking", fake_call_blocking)

    result = await fund_flow.get_hsgt_flow()

    assert result["unit"] == "亿元"
    assert result["points"] == []
