from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.market import KlineData, KlineItem
from app.financial_data.hk.schemas import HKStockQuote, HKStockQuotePage
from app.financial_data.stock.quotes.kline import get_kline
from app.financial_data.stock.quotes.realtime import RealtimeQuoteSet
from app.modules.portfolio.public import (
    PortfolioPositionCreate,
    PortfolioTransactionCreate,
    normalize_portfolio_stock_code,
)
from app.modules.portfolio.quotes import fetch_quote_batch


def test_normalize_portfolio_stock_code():
    # HK codes
    assert normalize_portfolio_stock_code("00700") == "00700"
    assert normalize_portfolio_stock_code("hk00700") == "00700"
    assert normalize_portfolio_stock_code("HK00700") == "00700"
    assert normalize_portfolio_stock_code("00700.hk") == "00700"
    assert normalize_portfolio_stock_code("00700.HK") == "00700"
    assert normalize_portfolio_stock_code("700") == "00700"
    assert normalize_portfolio_stock_code(" 09988 ") == "09988"

    # CN codes
    assert normalize_portfolio_stock_code("600519") == "600519"
    assert normalize_portfolio_stock_code("sh600519") == "600519"
    assert normalize_portfolio_stock_code("SZ000001") == "000001"
    assert normalize_portfolio_stock_code("000001") == "000001"

    # Invalid codes
    with pytest.raises(ValueError):
        normalize_portfolio_stock_code("invalid")
    with pytest.raises(ValueError):
        normalize_portfolio_stock_code("1234567")


def test_portfolio_create_schemas_hk_stock():
    tx_create = PortfolioTransactionCreate(
        stock_code="00700",
        side="buy",
        trade_price=380.5,
        trade_time=datetime(2026, 10, 5, 10, 0, 0),
        shares=100,
        fee=15.0,
    )
    assert tx_create.stock_code == "00700"

    pos_create = PortfolioPositionCreate(
        stock_code="hk09988",
        buy_price=85.0,
        buy_time=datetime(2026, 10, 5, 10, 0, 0),
        shares=500,
    )
    assert pos_create.stock_code == "09988"


@pytest.mark.asyncio
async def test_fetch_quote_batch_mixed_markets():
    mock_cn_set = RealtimeQuoteSet(
        source="tencent",
        quotes={"600519": {"price": 1600.0, "name": "贵州茅台", "change_pct": 1.5}},
        quote_sources={"600519": "tencent"},
    )
    mock_hk_page = HKStockQuotePage(
        items=[
            HKStockQuote(
                code="00700",
                name="腾讯控股",
                price=385.2,
                pre_close=380.0,
                change_pct=1.37,
            )
        ],
        total=1,
        page=1,
        page_size=1,
        source="sina",
    )

    with patch(
        "app.modules.portfolio.quotes.fetch_realtime_quote_set",
        new=AsyncMock(return_value=mock_cn_set),
    ) as mock_fetch_cn, patch(
        "app.modules.portfolio.quotes.hk_market_service.get_stock_quotes",
        new=AsyncMock(return_value=mock_hk_page),
    ) as mock_fetch_hk:
        batch = await fetch_quote_batch(["600519", "00700"])

        mock_fetch_cn.assert_awaited_once_with(["600519"])
        mock_fetch_hk.assert_awaited_once_with(codes=["00700"], page=1, page_size=1)

        assert batch.source == "mixed"
        assert "600519" in batch.quotes
        assert "00700" in batch.quotes
        assert batch.quotes["00700"]["name"] == "腾讯控股"
        assert batch.quotes["00700"]["last_close"] == 380.0


@pytest.mark.asyncio
async def test_get_kline_routes_hk_stock():
    mock_hk_kline = KlineData(
        code="00700",
        period="daily",
        adjust="none",
        source="sina",
        items=[
            KlineItem(
                date="2026-10-02",
                open=380.0,
                high=388.0,
                low=378.0,
                close=385.0,
                volume=1000000,
                amount=385000000,
            )
        ],
    )

    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_history",
        new=AsyncMock(return_value=mock_hk_kline),
    ) as mock_hk_history:
        result = await get_kline("00700", period="daily", adjust="none")

        mock_hk_history.assert_awaited_once_with(
            "00700",
            period="daily",
            adjust="none",
            start_date="",
            end_date="",
        )
        assert result.code == "00700"
        assert len(result.items) == 1
        assert result.items[0].close == 385.0


@pytest.mark.asyncio
async def test_resolve_stock_hk_search_fallback():
    from app.financial_data.hk.search_index import HKStockSearchRecord
    from app.modules.portfolio.transactions import _resolve_stock

    request = PortfolioTransactionCreate(
        stock_code="00700",
        side="buy",
        trade_price=380.0,
        trade_time=datetime(2026, 10, 5, 10, 0, 0),
        shares=100,
    )

    with patch("app.modules.portfolio.transactions.fetch_quotes", new=AsyncMock(return_value={})), \
         patch("app.modules.portfolio.transactions.portfolio_store.get_latest_stock_name", return_value=""), \
         patch("app.financial_data.hk.search_index.hk_stock_search_index.search", new=AsyncMock(return_value=[HKStockSearchRecord(code="00700", name="腾讯控股")])):
        resolved = await _resolve_stock(request, user_id=999)
        assert resolved is not None
        stock_name, quote = resolved
        assert stock_name == "腾讯控股"

