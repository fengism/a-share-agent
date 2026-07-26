import asyncio
from types import SimpleNamespace

from app.services.stock import name_map


def test_fetch_stock_name_map_remote_falls_back_to_sina(monkeypatch):
    """_fetch_stock_name_map_remote should fall back when earlier providers return too few rows."""

    monkeypatch.setattr(
        name_map,
        "_get_baidu_provider",
        lambda: SimpleNamespace(fetch_stock_names=lambda: []),
    )
    monkeypatch.setattr(
        name_map,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_stock_names=lambda: [{"code": "000001", "name": "平安银行"}]),
    )
    monkeypatch.setattr(
        name_map,
        "_get_sina_provider",
        lambda: SimpleNamespace(fetch_stock_names=lambda: [{"code": "600519", "name": "贵州茅台"}]),
    )

    async def fake_call_blocking(func, *args, **kwargs):
        kwargs.pop("semaphore", None)
        return func(*args, **kwargs)

    monkeypatch.setattr(name_map, "call_blocking", fake_call_blocking)

    result = asyncio.run(name_map._fetch_stock_name_map_remote())

    assert result == {"600519": "贵州茅台"}
