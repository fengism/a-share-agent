"""指数 K 线 10 年历史窗口与本地覆盖判定测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.market import KlineData, KlineItem
from app.financial_data.market.quotes.index_kline import get_index_kline


def _make_index_item(day: str) -> KlineItem:
    return KlineItem(
        code="000001",
        date=day,
        open=3000.0,
        high=3050.0,
        low=2980.0,
        close=3020.0,
        pre_close=3000.0,
        volume=1000000,
        amount=20000000,
    )


@pytest.mark.asyncio
async def test_get_index_kline_clamps_to_ten_years_and_returns_local_when_covered() -> None:
    # 模拟本地覆盖了 2026-09-28 ~ 2026-09-30
    local_items = [_make_index_item(d) for d in ("2026-09-28", "2026-09-29", "2026-09-30")]
    mock_local = KlineData(
        code="000001",
        period="daily",
        adjust="none",
        source="market_daily:confirmed",
        items=local_items,
    )

    with (
        patch(
            "app.financial_data.market.quotes.index_kline.load_local_daily_kline", AsyncMock(return_value=mock_local)
        ),
        patch("app.financial_data.market.quotes.index_kline._load_index_kline", AsyncMock()) as mock_upstream,
    ):
        # 请求 2000 年（早于 10 年），会被收敛到 10 年内；且由于本地完整覆盖 09-28~09-30，无需打上游
        result = await get_index_kline("000001", "daily", "2026-09-28", "2026-09-30")
        assert len(result.items) == 3
        assert result.items[0].date == "2026-09-28"
        assert result.items[-1].date == "2026-09-30"
        mock_upstream.assert_not_called()
