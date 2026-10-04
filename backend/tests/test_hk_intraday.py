import pytest

from app.financial_data.stock.quotes.intraday import get_intraday


@pytest.mark.asyncio
async def test_get_hk_stock_intraday():
    res = await get_intraday("00700")
    assert res.code == "00700"
    assert res.source == "腾讯港股分时"
    assert res.prev_close is not None
    assert len(res.items) > 0

    first = res.items[0]
    assert first.price is not None
    assert first.time.endswith("09:30") or "09:" in first.time


@pytest.mark.asyncio
async def test_get_hk_stock_intraday_with_prefix():
    res = await get_intraday("HK00700")
    assert res.code == "00700"
    assert len(res.items) > 0
