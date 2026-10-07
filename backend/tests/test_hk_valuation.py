from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.financial_data.hk.schemas import HKStockQuote, HKStockQuotePage, HKStockValuation
from app.financial_data.hk.service import hk_market_service
from app.financial_data.stock.profile.basic_info import get_basic_info
from app.financial_data.stock.valuation.orchestrator import get_valuation
from app.infrastructure.providers.tencent import tencent_provider
from app.main import app


def test_tencent_fetch_hk_stock_quotes_parsing():
    sample_response = (
        'v_r_hk00700="100~腾讯控股~00700~427.800~423.000~426.400~4938197.0~0~0~427.800~'
        '0~0~0~0~0~0~0~0~0~427.800~0~0~0~0~0~0~0~0~0~4938197.0~2026/10/06 11:57:38~4.800~'
        '1.13~429.200~425.600~427.800~4938197.0~2107339359.780~0~15.63~~0~0~0.85~'
        '38898.1667~38898.1667~TENCENT~1.24~675.700~411.000~0.66~2.03~0~0~0~0~0~14.34~'
        '2.99~0.05~100~-27.98~-2.77~GP~20.41~11.00~-0.56~-2.46~-6.56~9092605595.00~'
        '9092605595.00~14.80~5.315~426.743~-30.78~HKD~1~30";'
    )
    mock_resp = MagicMock()
    mock_resp.text = sample_response
    mock_resp.raise_for_status = MagicMock()

    with patch("app.infrastructure.providers.tencent._get_session") as mock_session:
        mock_session.return_value.get.return_value = mock_resp
        quotes = tencent_provider.fetch_hk_stock_quotes(["00700"])

    assert "00700" in quotes
    q = quotes["00700"]
    assert q["code"] == "00700"
    assert q["name"] == "腾讯控股"
    assert q["price"] == 427.8
    assert q["pe_ttm"] == 15.63
    assert q["pb"] == 1.24
    assert q["mcap"] == 38898.1667 * 1e8
    assert q["float_mcap"] == 38898.1667 * 1e8
    assert q["total_shares"] == 9092605595.0
    assert q["circulating_shares"] == 9092605595.0
    assert q["currency"] == "HKD"


@pytest.mark.asyncio
async def test_hk_market_service_get_stock_valuation():
    mock_metrics = {
        "00700": {
            "code": "00700",
            "name": "腾讯控股",
            "price": 427.8,
            "pe_ttm": 15.63,
            "pb": 1.24,
            "mcap": 3889816670000.0,
            "float_mcap": 3889816670000.0,
            "total_shares": 9092605595.0,
            "circulating_shares": 9092605595.0,
            "currency": "HKD",
        }
    }
    with patch.object(hk_market_service, "_fetch_tencent_metrics", new=AsyncMock(return_value=mock_metrics)):
        val = await hk_market_service.get_stock_valuation("00700")

    assert isinstance(val, HKStockValuation)
    assert val.code == "00700"
    assert val.name == "腾讯控股"
    assert val.pe_ttm == 15.63
    assert val.pb == 1.24
    assert val.market_cap == 3889816670000.0
    assert val.float_market_cap == 3889816670000.0
    assert val.currency == "HKD"


@pytest.mark.asyncio
async def test_hk_stock_quote_enriched_with_valuation():
    quote_items = [
        HKStockQuote(code="00700", name="腾讯控股", price=427.8),
    ]
    mock_metrics = {
        "00700": {
            "pe_ttm": 15.63,
            "pb": 1.24,
            "mcap": 3889816670000.0,
            "float_mcap": 3889816670000.0,
            "currency": "HKD",
        }
    }
    with patch.object(hk_market_service, "_fetch_tencent_metrics", new=AsyncMock(return_value=mock_metrics)):
        await hk_market_service._enrich_quotes_with_metrics(quote_items)

    assert quote_items[0].pe_ttm == 15.63
    assert quote_items[0].pb == 1.24
    assert quote_items[0].market_cap == 3889816670000.0
    assert quote_items[0].float_market_cap == 3889816670000.0
    assert quote_items[0].currency == "HKD"


@pytest.mark.asyncio
async def test_orchestrator_get_valuation_for_hk_stock():
    mock_val = HKStockValuation(
        code="00700",
        name="腾讯控股",
        pe_ttm=15.63,
        pb=1.24,
        market_cap=3889816670000.0,
        currency="HKD",
    )
    with patch.object(hk_market_service, "get_stock_valuation", new=AsyncMock(return_value=mock_val)):
        val = await get_valuation("00700")

    assert val.code == "00700"
    assert val.pe_ttm == 15.63
    assert val.pb == 1.24


@pytest.mark.asyncio
async def test_get_basic_info_for_hk_stock():
    mock_val = HKStockValuation(
        code="00700",
        name="腾讯控股",
        pe_ttm=15.63,
        pb=1.24,
        market_cap=3889816670000.0,
        float_market_cap=3889816670000.0,
        total_shares=9092605595.0,
        currency="HKD",
    )
    mock_page = HKStockQuotePage(
        items=[HKStockQuote(code="00700", name="腾讯控股", price=427.8)],
        total=1,
        page=1,
        page_size=1,
    )
    with (
        patch.object(hk_market_service, "get_stock_valuation", new=AsyncMock(return_value=mock_val)),
        patch.object(hk_market_service, "get_stock_quotes", new=AsyncMock(return_value=mock_page)),
    ):
        info = await get_basic_info("00700")

    assert info.code == "00700"
    assert info.name == "腾讯控股"
    assert info.pe_ttm == 15.63
    assert info.pb == 1.24
    assert info.market_cap == 3889816670000.0
    assert info.current_price == 427.8


@pytest.mark.asyncio
async def test_hk_stock_valuation_api_route():
    from app.api.auth.dependencies import require_active_user
    from app.domain.identity import UserRecord

    mock_val = HKStockValuation(
        code="00700",
        name="腾讯控股",
        pe_ttm=15.63,
        pb=1.24,
        market_cap=3889816670000.0,
        float_market_cap=3889816670000.0,
        currency="HKD",
    )
    app.dependency_overrides[require_active_user] = lambda: UserRecord(
        id="test-user",
        username="test",
        role="admin",
        is_active=True,
    )
    try:
        with patch.object(hk_market_service, "get_stock_valuation", new=AsyncMock(return_value=mock_val)):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/hk/stocks/00700/valuation")

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "00700"
        assert data["name"] == "腾讯控股"
        assert data["pe_ttm"] == 15.63
        assert data["pb"] == 1.24
        assert data["market_cap"] == 3889816670000.0
        assert data["currency"] == "HKD"
    finally:
        app.dependency_overrides.pop(require_active_user, None)
