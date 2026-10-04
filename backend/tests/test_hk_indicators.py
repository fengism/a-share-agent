from unittest.mock import AsyncMock, patch

import pytest

from app.domain.market import KlineData, KlineItem
from app.financial_data.stock.quotes.indicators import get_technical_indicators


@pytest.mark.asyncio
async def test_hk_technical_indicators():
    mock_items = [
        KlineItem(
            date=f"2026-01-{i:02d}",
            open=100.0 + i,
            close=101.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            volume=10000.0,
            amount=1000000.0,
        )
        for i in range(1, 35)
    ]
    mock_kline = KlineData(
        code="00700",
        period="daily",
        adjust="qfq",
        items=mock_items,
        source="sina",
    )

    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_history",
        new=AsyncMock(return_value=mock_kline),
    ) as mock_get_history:
        indicators = await get_technical_indicators("00700", period="daily")

        mock_get_history.assert_awaited_once_with(
            "00700",
            period="daily",
            start_date="",
            end_date="",
        )

        assert indicators.macd is not None
        assert indicators.rsi is not None
        assert indicators.kdj is not None
        assert indicators.series is not None
        assert len(indicators.series.dates) == 34
        assert len(indicators.series.dif) == 34
        assert len(indicators.series.macd_hist) == 34
        assert len(indicators.series.rsi) == 34
        assert len(indicators.series.k) == 34


@pytest.mark.asyncio
async def test_hk_annual_period():
    import pandas as pd

    from app.financial_data.hk.service import _resample_history, _validate_period

    assert _validate_period("annual") == "annual"

    df = pd.DataFrame({
        "date": pd.to_datetime(["2023-03-01", "2023-11-15", "2024-05-10"]),
        "open": [10.0, 12.0, 15.0],
        "high": [14.0, 13.0, 18.0],
        "low": [9.0, 11.0, 14.0],
        "close": [12.0, 11.5, 17.0],
        "volume": [100.0, 200.0, 300.0],
        "amount": [1000.0, 2000.0, 3000.0],
    })
    resampled = _resample_history(df, "annual")
    assert len(resampled) == 2
    assert resampled.iloc[0]["open"] == 10.0
    assert resampled.iloc[0]["high"] == 14.0
    assert resampled.iloc[0]["low"] == 9.0
    assert resampled.iloc[0]["close"] == 11.5
    assert resampled.iloc[0]["volume"] == 300.0
    assert resampled.iloc[1]["open"] == 15.0
    assert resampled.iloc[1]["close"] == 17.0


@pytest.mark.asyncio
async def test_hk_stock_history_adjust_empty():
    from app.api.routes.hk import get_hk_stock_history

    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_history",
        new=AsyncMock(return_value=KlineData(code="00700", period="daily", adjust="none", items=[], source="sina")),
    ) as mock_get_history:
        await get_hk_stock_history("00700", period="daily", adjust="", start_date="", end_date="")
        mock_get_history.assert_awaited_once_with(
            "00700",
            period="daily",
            adjust="none",
            start_date="",
            end_date="",
        )


