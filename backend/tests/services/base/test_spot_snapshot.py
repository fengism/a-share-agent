import asyncio
from types import SimpleNamespace

import pandas as pd

from app.services.base import spot_snapshot


def test_get_spot_snapshot_uses_akshare_as_last_fallback(monkeypatch):
    """get_spot_snapshot should fall back to Akshare when file/Sina/Eastmoney are unavailable."""
    df = pd.DataFrame([{"代码": "600519", "名称": "贵州茅台"}])

    monkeypatch.setattr(spot_snapshot._spot_snapshot_service, "get_cached", lambda: None)
    monkeypatch.setattr(spot_snapshot, "load_spot_snapshot_file", lambda: None)
    monkeypatch.setattr(spot_snapshot, "_fetch_spot_sina_vip", lambda: _none_df())
    monkeypatch.setattr(spot_snapshot, "_fetch_spot_east", lambda: _none_df())
    monkeypatch.setattr(
        spot_snapshot,
        "_get_akshare_provider",
        lambda: SimpleNamespace(fetch_spot_em=lambda: df),
    )

    cached = []
    monkeypatch.setattr(spot_snapshot._spot_snapshot_service, "set_cached", lambda value: cached.append(value))
    monkeypatch.setattr(spot_snapshot, "_save_spot_snapshot_file", lambda value: None)

    async def fake_call_blocking(func, *args, **kwargs):
        kwargs.pop("semaphore", None)
        return func(*args, **kwargs)

    monkeypatch.setattr(spot_snapshot, "call_blocking", fake_call_blocking)

    result = asyncio.run(spot_snapshot.get_spot_snapshot())

    assert result.equals(df)
    assert cached and cached[0].equals(df)


async def _none_df():
    """Return None for async fetch stubs."""
    return None
