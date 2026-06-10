import asyncio
import pandas as pd
from types import SimpleNamespace

from app.models.market import MarketIndices
from app.services.market import indices


def clear_indices_cache() -> None:
    """Remove the dated market_indices entry from the indices module cache.

    Return:
        None
    """
    indices.cache.delete(indices.dated_cache_key("market_indices"))


def test_get_indices_uses_akshare_em_first(monkeypatch):
    """get_indices returns akshare EastMoney data when earlier providers fail."""
    clear_indices_cache()

    async def fake_call_blocking(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(indices, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(
        indices,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_market_indices=lambda: (_ for _ in ()).throw(RuntimeError("east down"))),
    )
    monkeypatch.setattr(
        indices,
        "_get_sina_provider",
        lambda: SimpleNamespace(fetch_market_indices=lambda: (_ for _ in ()).throw(RuntimeError("sina down"))),
    )
    monkeypatch.setattr(
        indices,
        "_get_akshare_provider",
        lambda: SimpleNamespace(
            fetch_market_indices=lambda: pd.DataFrame([
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
            fetch_market_indices_sina=lambda: (_ for _ in ()).throw(RuntimeError("unused")),
        ),
    )

    result = asyncio.run(indices.get_indices())

    assert result.source == "em_ak"
    assert result.indices[0].code == "000001"
    assert result.indices[0].price == 3000
    assert result.total_amount == 200


def test_get_indices_falls_back_to_east_direct(monkeypatch):
    """get_indices uses the EastMoney direct provider when it is available first."""
    clear_indices_cache()

    async def fake_call_blocking(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(indices, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(
        indices,
        "_get_akshare_provider",
        lambda: SimpleNamespace(
            fetch_market_indices=lambda: (_ for _ in ()).throw(RuntimeError("em down")),
            fetch_market_indices_sina=lambda: (_ for _ in ()).throw(RuntimeError("unused")),
        ),
    )
    monkeypatch.setattr(
        indices,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(
            fetch_market_indices=lambda: pd.DataFrame([
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
            ])
        ),
    )

    result = asyncio.run(indices.get_indices())

    assert result.source == "east_direct"
    assert result.indices[0].price == 100000
    assert result.indices[0].change_pct == 120
    assert result.total_amount == 300


def test_get_indices_falls_back_to_sina_direct(monkeypatch):
    """get_indices falls back to the Sina direct provider when EastMoney and Akshare fail."""
    clear_indices_cache()

    async def fake_call_blocking(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(indices, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(
        indices,
        "_get_akshare_provider",
        lambda: SimpleNamespace(
            fetch_market_indices=lambda: (_ for _ in ()).throw(RuntimeError("em down")),
            fetch_market_indices_sina=lambda: (_ for _ in ()).throw(RuntimeError("sina ak down")),
        ),
    )
    monkeypatch.setattr(
        indices,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_market_indices=lambda: (_ for _ in ()).throw(RuntimeError("east down"))),
    )
    monkeypatch.setattr(
        indices,
        "build_indices_from_sina",
        lambda df: MarketIndices(indices=[indices.IndexItem(code="000001", name="上证指数", amount=400)]),
    )
    monkeypatch.setattr(
        indices,
        "_get_sina_provider",
        lambda: SimpleNamespace(fetch_market_indices=lambda: pd.DataFrame([{"symbol": "sh000001"}])),
    )

    result = asyncio.run(indices.get_indices())

    assert result.source == "sina_direct"
    assert result.indices[0].code == "000001"
    assert result.total_amount == 400
