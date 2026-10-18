"""潜力股历史表现复盘：计算挖掘日之后 N 个交易日的收益与超额收益。"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
import time
from datetime import UTC, date, datetime, timedelta

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.financial_data.market.public import get_index_kline
from app.financial_data.stock.public import get_historical_bars
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.modules.potential.persistence import repository
from app.modules.potential.schemas import (
    PotentialDailyResult,
    PotentialPerformanceItem,
    PotentialPerformanceSummary,
)

logger = logging.getLogger(__name__)

_MAX_PERFORMANCE_ITEMS = 20
_PERFORMANCE_CONCURRENCY = 6
_PERFORMANCE_TIMEOUT_SECONDS = 20.0
_PERFORMANCE_CACHE_TTL_SECONDS = 3600
_PERFORMANCE_DIR = DATA_DIR / "potential_performance"
_INDEX_SYMBOL = "000300"


def _cache_path(date_text: str, days: int):
    return _PERFORMANCE_DIR / f"{date_text}_{days}.json"


def _load_cached(date_text: str, days: int) -> PotentialPerformanceSummary | None:
    path = _cache_path(date_text, days)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cached_at = float(payload.get("cached_at", 0))
        if time.time() - cached_at > _PERFORMANCE_CACHE_TTL_SECONDS:
            return None
        summary: PotentialPerformanceSummary = PotentialPerformanceSummary.model_validate(payload.get("data"))
        return summary
    except Exception as error:
        logger.debug("读取潜力股表现缓存失败 %s/%s: %s", date_text, days, error)
        return None


def _save_cached(summary: PotentialPerformanceSummary) -> None:
    try:
        atomic_write_json(
            _cache_path(summary.date, summary.days),
            {"cached_at": time.time(), "data": summary.model_dump()},
            indent=2,
        )
    except Exception as error:
        logger.warning("写入潜力股表现缓存失败 %s/%s: %s", summary.date, summary.days, error)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _close_series(bars) -> list[tuple[str, float]]:
    series: list[tuple[str, float]] = []
    for item in bars.items:
        close = float(item.close)
        if not math.isfinite(close) or close <= 0:
            continue
        series.append((str(item.date)[:10], close))
    return series


async def _benchmark_return(market_date: date, days: int) -> tuple[float | None, bool]:
    start = market_date - timedelta(days=10)
    end = market_date + timedelta(days=days * 2 + 20)
    try:
        bars = await asyncio.wait_for(
            get_index_kline(
                _INDEX_SYMBOL,
                period="daily",
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            ),
            timeout=_PERFORMANCE_TIMEOUT_SECONDS,
        )
    except Exception as error:
        logger.debug("潜力股基准指数获取失败: %s", error)
        return None, True
    series = _close_series(bars)
    entry_index = next((index for index, (date_text, _) in enumerate(series) if date_text == market_date.isoformat()), None)
    if entry_index is None:
        return None, True
    if entry_index + days >= len(series):
        return None, False
    entry_close = series[entry_index][1]
    exit_close = series[entry_index + days][1]
    return (round((exit_close / entry_close - 1) * 100, 2) if entry_close > 0 else None), True


async def _evaluate_item(
    item,
    market_date: date,
    days: int,
    benchmark_return: float | None,
) -> PotentialPerformanceItem | None:
    start = market_date - timedelta(days=5)
    end = market_date + timedelta(days=days * 2 + 20)
    try:
        bars = await asyncio.wait_for(
            get_historical_bars(
                item.code,
                start,
                end,
                period="daily",
                adjust="qfq",
            ),
            timeout=_PERFORMANCE_TIMEOUT_SECONDS,
        )
    except Exception as error:
        logger.debug("潜力股表现行情获取失败 %s: %s", item.code, error)
        return None
    series = _close_series(bars)
    entry_index = next((index for index, (date_text, _) in enumerate(series) if date_text == market_date.isoformat()), None)
    if entry_index is None or entry_index + days >= len(series):
        return None
    entry_price = series[entry_index][1]
    exit_price = series[entry_index + days][1]
    if entry_price <= 0:
        return None
    window = [close for _, close in series[entry_index : entry_index + days + 1]]
    return_pct = (exit_price / entry_price - 1) * 100
    max_return = max((close / entry_price - 1) * 100 for close in window)
    max_drawdown = min((close / entry_price - 1) * 100 for close in window)
    excess = return_pct - benchmark_return if benchmark_return is not None else None
    return PotentialPerformanceItem(
        code=item.code,
        name=item.name,
        industry=item.industry,
        entry_price=round(entry_price, 2),
        exit_price=round(exit_price, 2),
        return_pct=round(return_pct, 2),
        benchmark_return_pct=benchmark_return,
        excess_return_pct=round(excess, 2) if excess is not None else None,
        max_return_pct=round(max_return, 2),
        max_drawdown_pct=round(max_drawdown, 2),
    )


async def compute_potential_performance(date_text: str, days: int = 5) -> PotentialPerformanceSummary | None:
    """计算指定挖掘日、指定持有期的前瞻表现。"""
    market_date = _parse_date(date_text)
    if market_date is None:
        return None
    cached = _load_cached(market_date.isoformat(), days)
    if cached is not None:
        return cached
    result: PotentialDailyResult | None = await call_blocking(
        repository.load_potential_result,
        market_date.isoformat(),
        semaphore=misc_semaphore,
    )
    if result is None:
        return None
    if not result.items:
        summary = PotentialPerformanceSummary(
            date=market_date.isoformat(),
            days=days,
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            item_count=0,
            evaluated_count=0,
            message="该日期没有命中标的",
        )
        _save_cached(summary)
        return summary

    benchmark_return, forward_data_available = await _benchmark_return(market_date, days)
    if not forward_data_available:
        summary = PotentialPerformanceSummary(
            date=market_date.isoformat(),
            days=days,
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            item_count=len(result.items),
            evaluated_count=0,
            message=f"暂无足够的前瞻数据（需要至少 {days} 个交易日）",
        )
        _save_cached(summary)
        return summary
    semaphore = asyncio.Semaphore(_PERFORMANCE_CONCURRENCY)

    async def evaluate(item):
        async with semaphore:
            return await _evaluate_item(item, market_date, days, benchmark_return)

    targets = result.items[:_MAX_PERFORMANCE_ITEMS]
    evaluated = [item for item in await asyncio.gather(*(evaluate(item) for item in targets)) if item is not None]
    evaluated.sort(key=lambda item: (-(item.excess_return_pct or -999), -(item.return_pct or -999)))
    returns = [item.return_pct for item in evaluated if item.return_pct is not None]
    excess_returns = [item.excess_return_pct for item in evaluated if item.excess_return_pct is not None]
    message = None
    if not evaluated:
        message = f"暂无足够的前瞻数据（需要至少 {days} 个交易日）"
    elif len(evaluated) < len(targets):
        message = f"已评估 {len(evaluated)}/{len(targets)} 只，部分标的停牌或数据不足"
    summary = PotentialPerformanceSummary(
        date=market_date.isoformat(),
        days=days,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        item_count=len(result.items),
        evaluated_count=len(evaluated),
        win_rate=round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else None,
        average_return_pct=round(sum(returns) / len(returns), 2) if returns else None,
        median_return_pct=round(statistics.median(returns), 2) if returns else None,
        average_excess_pct=round(sum(excess_returns) / len(excess_returns), 2) if excess_returns else None,
        benchmark_return_pct=benchmark_return,
        message=message,
        items=evaluated,
    )
    _save_cached(summary)
    return summary
