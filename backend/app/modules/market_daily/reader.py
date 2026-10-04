"""独立日行情库的 local-first 读取适配层。"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from app.domain.market import KlineData, KlineItem
from app.modules.market_daily.models import MarketDailyBar
from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH
from app.modules.market_daily.repository import MarketDailyBarRepository

logger = logging.getLogger(__name__)

_market_daily_repository = MarketDailyBarRepository(MARKET_DAILY_DATABASE_PATH)


def _to_kline_item(bar: MarketDailyBar) -> KlineItem:
    amplitude = None
    if bar.pre_close is not None and bar.pre_close > 0 and bar.high is not None and bar.low is not None:
        amplitude = (bar.high - bar.low) / bar.pre_close * 100
    return KlineItem(
        code=bar.code,
        date=bar.trade_date.isoformat(),
        open=bar.open if bar.open is not None else bar.close,
        close=bar.close,
        high=bar.high if bar.high is not None else bar.close,
        low=bar.low if bar.low is not None else bar.close,
        volume=bar.volume or 0,
        amount=bar.amount or 0,
        turnover_pct=bar.turnover_pct,
        amplitude=amplitude,
        change_pct=bar.change_pct,
        pre_close=bar.pre_close,
    )


async def load_local_daily_kline(
    *,
    market: str,
    instrument_type: str,
    code: str,
    start_date: date,
    end_date: date,
    adjust: str = "",
) -> KlineData | None:
    """读取已有日行情；不根据当前时刻或确认状态过滤。读取失败时交给上游回退。"""
    try:
        await asyncio.to_thread(_market_daily_repository.initialize)
        bars = await asyncio.to_thread(
            _market_daily_repository.list_bars,
            market=market,
            instrument_type=instrument_type,
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as error:
        logger.warning(
            "本地日行情读取失败，回退外部数据源: market=%s type=%s code=%s error=%s",
            market,
            instrument_type,
            code,
            type(error).__name__,
        )
        return None
    if not bars:
        return None
    statuses = sorted({bar.verification_status for bar in bars})
    return KlineData(
        code=code,
        period="daily",
        adjust=adjust,
        source=f"market_daily:{'+'.join(statuses)}",
        adjustment_verified=True,
        items=[_to_kline_item(bar) for bar in bars],
    )


def merge_local_daily_kline(upstream: KlineData, local: KlineData | None) -> KlineData:
    """以本地持久化日线覆盖同日上游值，并保留上游独有历史。"""
    if local is None or not local.items:
        return upstream
    upstream_by_date = {item.date: item for item in upstream.items}
    merged_by_date = dict(upstream_by_date)
    for item in local.items:
        upstream_item = upstream_by_date.get(item.date)
        if upstream_item is not None and item.turnover_pct is None:
            item = item.model_copy(update={"turnover_pct": upstream_item.turnover_pct})
        merged_by_date[item.date] = item
    sources = "+".join(part for part in (local.source, upstream.source) if part)
    return upstream.model_copy(
        update={
            "source": sources or "market_daily",
            "items": sorted(merged_by_date.values(), key=lambda item: item.date),
        }
    )
