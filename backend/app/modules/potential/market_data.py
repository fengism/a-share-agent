"""潜力股日线行情获取：优先新接口 get_kline，旧接口 get_historical_bars 兜底。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.financial_data.stock.public import get_historical_bars, get_kline

logger = logging.getLogger(__name__)


async def fetch_daily_bars(code: str, start: date, end: date, *, adjust: str = "qfq") -> Any:
    """获取 [start, end] 区间的日线数据。

    get_kline 支持 ISO 日期字符串且为当前维护的接口；调用失败时退回
    get_historical_bars，保证行情源短时不可用时不中断整批挖掘。
    """
    try:
        return await get_kline(
            code,
            "daily",
            start.isoformat(),
            end.isoformat(),
            adjust=adjust,
        )
    except Exception as error:
        logger.warning("get_kline 获取 %s 日线失败，回退 get_historical_bars: %s", code, error)
    return await get_historical_bars(
        code,
        start,
        end,
        period="daily",
        adjust=adjust,
    )
