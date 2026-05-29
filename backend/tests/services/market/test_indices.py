import pandas as pd
import pytest

from app.models.market import MarketIndices
from app.services.market import indices


def clear_indices_cache() -> None:
    indices.cache.delete(indices.dated_cache_key("market_indices"))


@pytest.mark.asyncio
async def test_get_indices_uses_akshare_em_first(monkeypatch):
    clear_indices_cache()

    monkeypatch.setattr(
        indices._akshare_provider,
        "fetch_market_indices",
        lambda: pd.DataFrame([
            {
                "代码": "000001",
                "名称": "上证指数",
                "最新价": 3000,
                "涨跌幅": 1.2,
                "成交量": 100,
                "成交额": 200,
                "今开": 2990,
                "最高": 3010,
                "最低": 2980,
                "振幅": 1.5,
                "昨收": 2995,
            }
        ]),
    )

    result = await indices.get_indices()

    assert result.source == "em_ak"
    assert result.indices[0].code == "000001"
    assert result.indices[0].price == 3000
    assert result.total_amount == 200


@pytest.mark.asyncio
async def test_get_indices_falls_back_to_east_direct(monkeypatch):
    clear_indices_cache()

    monkeypatch.setattr(indices._akshare_provider, "fetch_market_indices", lambda: (_ for _ in ()).throw(RuntimeError("em down")))
    monkeypatch.setattr(
        indices._eastmoney_provider,
        "fetch_market_indices_direct",
        lambda: pd.DataFrame([
            {
                "代码": "399001",
                "名称": "深证成指",
                "最新价": 100000,
                "涨跌幅": 120,
                "成交量": 100,
                "成交额": 300,
                "今开": 99000,
                "最高": 101000,
                "最低": 98000,
                "振幅": 150,
                "昨收": 99500,
            }
        ]),
    )

    result = await indices.get_indices()

    assert result.source == "east_direct"
    assert result.indices[0].price == 1000
    assert result.indices[0].change_pct == 1.2
    assert result.total_amount == 300


@pytest.mark.asyncio
async def test_get_indices_falls_back_to_sina_direct(monkeypatch):
    clear_indices_cache()

    monkeypatch.setattr(indices._akshare_provider, "fetch_market_indices", lambda: (_ for _ in ()).throw(RuntimeError("em down")))
    monkeypatch.setattr(indices._eastmoney_provider, "fetch_market_indices_direct", lambda: (_ for _ in ()).throw(RuntimeError("east down")))
    monkeypatch.setattr(indices._akshare_provider, "fetch_market_indices_sina", lambda: (_ for _ in ()).throw(RuntimeError("sina ak down")))
    monkeypatch.setattr(
        indices,
        "build_indices_from_sina",
        lambda df: MarketIndices(indices=[indices.IndexItem(code="000001", name="上证指数", amount=400)]),
    )
    monkeypatch.setattr(indices._sina_provider, "fetch_market_indices_direct", lambda: pd.DataFrame([{"symbol": "sh000001"}]))

    result = await indices.get_indices()

    assert result.source == "sina_direct"
    assert result.indices[0].code == "000001"
    assert result.total_amount == 400
