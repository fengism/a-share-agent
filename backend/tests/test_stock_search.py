import pytest

from app.financial_data.stock.profile.search import search_stocks


@pytest.mark.asyncio
async def test_search_stocks_with_hk_code():
    results = await search_stocks("00700")
    assert any(item.code == "00700" and item.market == "hk" for item in results)
    assert any("腾讯" in item.name for item in results)


@pytest.mark.asyncio
async def test_search_stocks_with_hk_name():
    results = await search_stocks("腾讯")
    assert any(item.code == "00700" and item.market == "hk" for item in results)


@pytest.mark.asyncio
async def test_search_stocks_with_a_share():
    results = await search_stocks("600519")
    assert any(item.code == "600519" and item.market == "cn" for item in results)


@pytest.mark.asyncio
async def test_search_stocks_dual_listed():
    results = await search_stocks("中芯国际")
    codes = {item.code for item in results}
    # Should contain both A-share (688981) and HK-share (00981)
    assert "688981" in codes
    assert "00981" in codes
