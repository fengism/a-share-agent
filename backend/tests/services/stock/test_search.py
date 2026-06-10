import asyncio
from types import SimpleNamespace

import pandas as pd

from app.models.stock import StockSearchItem
from app.services.stock import search


def test_search_stocks_merges_local_remote_and_enriches_spot(monkeypatch):
    """search_stocks should merge local and remote matches, then enrich from cached spot data."""

    async def fake_name_map():
        return {
            "600519": "贵州茅台",
            "000001": "平安银行",
        }

    async def fake_call_blocking(func, *args, **kwargs):
        return [
            StockSearchItem(code="600519", name="贵州茅台"),
            StockSearchItem(code="600036", name="招商银行"),
        ]

    monkeypatch.setattr(search, "get_stock_name_map", fake_name_map)
    monkeypatch.setattr(
        search,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(search_stocks=lambda query, count: []),
    )
    monkeypatch.setattr(search, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(
        search.cache,
        "get",
        lambda key: pd.DataFrame(
            [
                {"代码": "600519", "最新价": 1688.0, "涨跌幅": 1.23},
                {"代码": "600036", "最新价": 44.5, "涨跌幅": -0.4},
            ]
        )
        if key == "stock_spot_all"
        else None,
    )

    result = asyncio.run(search.search_stocks("茅台"))

    assert [item.code for item in result] == ["600519", "600036"]
    assert result[0].price == 1688.0
    assert result[1].change_pct == -0.4


def test_search_stocks_returns_local_results_when_remote_fails(monkeypatch):
    """search_stocks should still return local hits when remote suggestion lookup fails."""

    async def fake_name_map():
        return {"600519": "贵州茅台"}

    async def fake_call_blocking(func, *args, **kwargs):
        raise RuntimeError("remote failed")

    monkeypatch.setattr(search, "get_stock_name_map", fake_name_map)
    monkeypatch.setattr(
        search,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(search_stocks=lambda query, count: []),
    )
    monkeypatch.setattr(search, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(search.cache, "get", lambda key: None)

    result = asyncio.run(search.search_stocks("600519"))

    assert result == [StockSearchItem(code="600519", name="贵州茅台")]
