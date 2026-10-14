from unittest.mock import patch

import pytest

from app.core.market import normalize_index_code, normalize_index_symbol
from app.domain.market import KlineData, KlineItem
from app.financial_data.market.quotes.volume import (
    _INDEX_MARKETS,
    _INDEX_SYMBOLS,
    get_market_volume,
)


def test_index_normalization_beijing():
    assert normalize_index_symbol("899050") == "bj899050"
    assert normalize_index_symbol("bj899050") == "bj899050"
    assert normalize_index_code("bj899050") == "899050"
    assert normalize_index_symbol("000001") == "sh000001"
    assert normalize_index_symbol("399001") == "sz399001"


def test_index_symbols_include_beijing():
    assert "899050" in _INDEX_SYMBOLS
    assert _INDEX_MARKETS["899050"] == "beijing"
    assert len(_INDEX_SYMBOLS) == 3


@pytest.mark.asyncio
async def test_get_market_volume_aggregates_three_markets():
    def fake_kline(symbol: str, **kwargs):
        amt = {"000001": 5000.0, "399001": 6000.0, "899050": 200.0}.get(symbol, 0.0)
        vol = {"000001": 50.0, "399001": 60.0, "899050": 2.0}.get(symbol, 0.0)
        return KlineData(
            code=symbol,
            period="daily",
            adjust="",
            source="test",
            items=[
                KlineItem(
                    code=symbol,
                    date="2026-10-13",
                    open=100.0,
                    close=101.0,
                    high=102.0,
                    low=99.0,
                    volume=vol,
                    amount=amt,
                )
            ],
        )

    with patch("app.financial_data.market.quotes.volume.get_index_kline", side_effect=fake_kline):
        resp = await get_market_volume(start_date="2026-10-13", end_date="2026-10-13")
        assert resp.partial is False
        assert len(resp.items) == 1
        item = resp.items[0]
        assert item.date == "2026-10-13"
        assert item.amount == 11200.0
        assert item.volume == 112.0
        assert resp.market_sources == {
            "shanghai": "test",
            "shenzhen": "test",
            "beijing": "test",
        }
