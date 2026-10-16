"""每日潜力股挖掘：多策略信号融合 + 风控过滤，按日持久化。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, time, timedelta

import pandas as pd

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.financial_data.market.public import get_trading_calendar_view
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE
from app.financial_data.stock.public import (
    get_exchange_stock_master,
    get_historical_bars,
    get_spot_snapshot,
)
from app.modules.potential.persistence import repository
from app.modules.potential.schemas import (
    PotentialDailyResult,
    PotentialDateItem,
    PotentialStockItem,
)
from app.modules.quant.engine import build_target_positions
from app.modules.quant.public import get_strategy_registry
from app.modules.screener.strategy_screening import SCREENER_STRATEGY_KEYS

logger = logging.getLogger(__name__)

# 候选池：兼顾高流动性龙头与中盘活跃成长股
_MAX_CANDIDATES = 300
_MIN_AMOUNT_YI = 0.8
_MIN_LISTING_DAYS = 365
_MAX_SIGNAL_AGE_DAYS = 5
_MAX_OUTPUT = 50
_MAX_CONCURRENCY = 6
_HISTORY_DAYS = 420
_TRADING_CALENDAR_LOOKBACK_DAYS = 370
_DAILY_MINING_CUTOFF = time(15, 10)

# 策略权重：形态/底部类罕见信号权重更高
_STRATEGY_WEIGHTS: dict[str, float] = {
    "bull_trend": 1.0,
    "ma_golden_cross": 1.2,
    "volume_breakout": 1.2,
    "shrink_pullback": 1.0,
    "bottom_volume": 1.5,
    "one_yang_three_yin": 1.5,
    "box_oscillation": 1.0,
}
# 信号新鲜度加成：3 个交易日内触发的信号额外 +50% 权重
_FRESH_SIGNAL_DAYS = 3


def _normalize_code(value: object) -> str:
    text = str(value or "").strip()
    if text[:2].upper() in {"SH", "SZ", "BJ"}:
        text = text[2:]
    return text.zfill(6) if text.isdigit() else text


def _select_candidates(
    df: pd.DataFrame | None,
    master_records: list,
) -> list[dict]:
    """从全市场快照筛出风控合格的候选池（分层覆盖核心高成交龙头与中盘活跃成长股）。"""
    if df is None or df.empty:
        return []
    frame = df.copy()
    frame["代码"] = frame["代码"].map(_normalize_code)
    frame = frame.drop_duplicates(subset=["代码"], keep="first")

    by_code = {record.code: record for record in master_records}
    frame["board"] = frame["代码"].map({code: record.board for code, record in by_code.items()})
    frame["listing_date"] = frame["代码"].map({code: record.listing_date for code, record in by_code.items()})
    frame["amount_yi"] = pd.to_numeric(frame.get("成交额"), errors="coerce") / 1e8
    frame["turnover_pct"] = pd.to_numeric(frame.get("换手率"), errors="coerce")

    name_text = frame["名称"].astype(str)
    mask = ~(name_text.str.upper().str.contains("ST", na=False) | name_text.str.contains("退", na=False))
    mask &= frame["amount_yi"].notna() & (frame["amount_yi"] >= _MIN_AMOUNT_YI)
    listing_days = (pd.Timestamp.now() - pd.to_datetime(frame["listing_date"], errors="coerce")).dt.days
    mask &= listing_days.isna() | (listing_days >= _MIN_LISTING_DAYS)
    frame = frame[mask]

    # 分层挑选候选池：
    # 1. 头部高流动性龙头（成交额前 150 名）
    # 2. 中盘活跃成长股票（成交额 0.8~15 亿且换手率 2%~18% 之间前 150 名）
    head_candidates = frame.sort_values(by="amount_yi", ascending=False).head(150)
    mid_pool = frame[
        (frame["amount_yi"] <= 15.0)
        & (frame["turnover_pct"] >= 2.0)
        & (frame["turnover_pct"] <= 18.0)
    ]
    mid_candidates = mid_pool.sort_values(by="turnover_pct", ascending=False).head(150)
    merged_frame = pd.concat([head_candidates, mid_candidates]).drop_duplicates(subset=["代码"], keep="first")
    selected = merged_frame.head(_MAX_CANDIDATES)

    return [
        {
            "code": str(row["代码"]),
            "name": str(row["名称"]),
            "price": pd.to_numeric(row.get("最新价"), errors="coerce"),
            "change_pct": pd.to_numeric(row.get("涨跌幅"), errors="coerce"),
            "market_cap": pd.to_numeric(row.get("总市值"), errors="coerce") / 1e8,
            "turnover_pct": pd.to_numeric(row.get("换手率"), errors="coerce"),
            "amount": row["amount_yi"],
        }
        for _, row in selected.iterrows()
    ]


def _float_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _latest_entry_index(positions: list[int]) -> int | None:
    for index in range(len(positions) - 1, -1, -1):
        if positions[index] == 1 and (index == 0 or positions[index - 1] != 1):
            return index
    return None


def _evaluate_strategies(
    bars_items: list,
    strategy_snapshots: dict,
) -> tuple[list[str], str, int | None, float]:
    """对单只股票的全部策略求信号（同步，在线程池中执行）。"""
    hits: list[str] = []
    latest_signal_date = ""
    signal_age: int | None = None
    score = 0.0
    for key, snapshot in strategy_snapshots.items():
        try:
            positions = build_target_positions(bars_items, snapshot)
        except Exception:
            continue
        if not positions or positions[-1] != 1:
            continue
        entry_index = _latest_entry_index(positions)
        if entry_index is None:
            continue
        age = len(positions) - 1 - entry_index
        # 信号时效性风控：只保留最近 _MAX_SIGNAL_AGE_DAYS (5个交易日) 内触发 entry 的新鲜信号
        if age > _MAX_SIGNAL_AGE_DAYS:
            continue
        weight = _STRATEGY_WEIGHTS.get(key, 1.0)
        if age <= _FRESH_SIGNAL_DAYS:
            weight *= 1.5
        score += weight
        hits.append(snapshot.definition.name)
        if signal_age is None or age < signal_age:
            signal_age = age
            latest_signal_date = bars_items[entry_index].date
    return hits, latest_signal_date, signal_age, score


def _normalize_shanghai_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=SHANGHAI_TIMEZONE)
    return now.astimezone(SHANGHAI_TIMEZONE)


async def resolve_potential_market_date(now: datetime | None = None) -> date | None:
    """解析最近一个已经收盘的真实 A 股交易日。"""
    local_now = _normalize_shanghai_now(now)
    latest_candidate = local_now.date()
    if local_now.time().replace(tzinfo=None) < _DAILY_MINING_CUTOFF:
        latest_candidate -= timedelta(days=1)

    try:
        calendar = await get_trading_calendar_view(
            latest_candidate - timedelta(days=_TRADING_CALENDAR_LOOKBACK_DAYS),
            latest_candidate,
        )
    except Exception:
        logger.exception("潜力股交易日解析失败: date=%s", latest_candidate)
        return None

    if calendar.degraded:
        logger.warning("潜力股任务跳过：交易日历处于降级状态")
        return None

    trade_dates: list[date] = []
    for value in calendar.trade_dates:
        try:
            trade_date = date.fromisoformat(value)
        except (TypeError, ValueError):
            logger.warning("潜力股交易日历包含无效日期: %r", value)
            continue
        if trade_date <= latest_candidate:
            trade_dates.append(trade_date)
    if not trade_dates:
        logger.warning("潜力股任务跳过：%s 前没有可用交易日", latest_candidate)
        return None
    return max(trade_dates)


async def mine_potential_stocks(market_date: date) -> PotentialDailyResult:
    """按指定交易日执行一轮挖掘：候选筛选 → 多策略信号 → 融合评分。"""
    df, master = await asyncio.gather(
        get_spot_snapshot(),
        get_exchange_stock_master(),
    )
    candidates = await call_blocking(
        _select_candidates,
        df,
        master.records if master is not None else [],
        semaphore=misc_semaphore,
    )
    registry = get_strategy_registry()
    strategy_snapshots = {
        key: registry.resolve(key, None, {}) for key in sorted(SCREENER_STRATEGY_KEYS)
    }

    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    start_date = market_date - timedelta(days=_HISTORY_DAYS)
    end_date = market_date
    items: list[PotentialStockItem] = []
    failed = 0

    async def evaluate(candidate: dict) -> None:
        nonlocal failed
        code = candidate["code"]
        async with semaphore:
            try:
                bars = await get_historical_bars(
                    code, start_date, end_date, period="daily", adjust="qfq",
                )
            except Exception as error:
                failed += 1
                logger.debug("潜力股评估行情获取失败 %s: %s", code, error)
                return
            if not bars.items:
                failed += 1
                return

        final_bar = bars.items[-1]
        prev_bar = bars.items[-2] if len(bars.items) >= 2 else None

        prev_close = prev_bar.close if prev_bar else final_bar.close
        calc_change_pct = (
            round((final_bar.close - prev_close) / prev_close * 100, 2)
            if prev_close and prev_close > 0
            else _float_or_none(candidate.get("change_pct"))
        )

        # 当日跌幅与形态风控：排除当日收盘跌幅超 3% 或大阴线杀跌股票（实体跌幅超 3.5%）
        if calc_change_pct is not None and calc_change_pct < -3.0:
            return
        if final_bar.open > 0 and (final_bar.close - final_bar.open) / final_bar.open < -0.035:
            return

        hits, latest_signal_date, signal_age, score = await call_blocking(
            _evaluate_strategies,
            bars.items,
            strategy_snapshots,
            semaphore=misc_semaphore,
        )
        if not hits:
            return

        # 以交易日官方日K线收盘价格与精确涨跌幅为准，确保与行情详情及K线完全对齐
        exact_price = round(final_bar.close, 2) if final_bar.close else _float_or_none(candidate.get("price"))

        items.append(
            PotentialStockItem(
                code=code,
                name=candidate["name"],
                price=exact_price,
                change_pct=calc_change_pct,
                market_cap=_float_or_none(candidate.get("market_cap")),
                turnover_pct=_float_or_none(candidate.get("turnover_pct")),
                amount=_float_or_none(candidate.get("amount")),
                strategies=hits,
                signal_date=latest_signal_date,
                signal_age_days=signal_age,
                score=round(score, 2),
            )
        )

    await asyncio.gather(*(evaluate(candidate) for candidate in candidates))
    items.sort(key=lambda item: (-item.score, -(item.amount or 0)))

    return PotentialDailyResult(
        date=end_date.isoformat(),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        universe_size=len(candidates),
        evaluated=len(candidates) - failed,
        failed_count=failed,
        items=items[:_MAX_OUTPUT],
    )


async def run_daily_mining(
    force: bool = False,
    now: datetime | None = None,
) -> PotentialDailyResult | None:
    """挖掘最近已收盘交易日；已有结果时跳过（force 可强制重跑）。"""
    market_date = await resolve_potential_market_date(now)
    if market_date is None:
        return None

    market_date_text = market_date.isoformat()
    if not force and repository.has_potential_result(market_date_text):
        return repository.load_potential_result(market_date_text)
    result = await mine_potential_stocks(market_date)
    await call_blocking(repository.save_potential_result, result, semaphore=misc_semaphore)
    logger.info(
        "潜力股挖掘完成: date=%s universe=%s evaluated=%s hits=%s",
        result.date, result.universe_size, result.evaluated, len(result.items),
    )
    try:
        from app.core.events import event_bus
        await event_bus.publish(result, name="potential_stocks.mined")
    except Exception:  # noqa: BLE001 - 事件发布异常绝不阻断挖掘返回
        logger.warning("发布潜力股挖掘完成事件失败: date=%s", result.date, exc_info=True)
    return result


async def run_scheduled_daily_mining(
    now: datetime | None = None,
) -> PotentialDailyResult | None:
    """仅在真实交易日的收盘截止时间后执行自动挖掘。"""
    local_now = _normalize_shanghai_now(now)
    if local_now.time().replace(tzinfo=None) < _DAILY_MINING_CUTOFF:
        return None

    market_date = await resolve_potential_market_date(local_now)
    if market_date is None or market_date != local_now.date():
        return None
    return await run_daily_mining(force=False, now=local_now)


async def get_potential_result(date: str | None = None) -> PotentialDailyResult | None:
    """获取指定日期结果；未指定时返回最近一份。"""
    if date is not None:
        return await call_blocking(repository.load_potential_result, date, semaphore=misc_semaphore)
    dates = await call_blocking(repository.list_potential_dates, 1, semaphore=misc_semaphore)
    if not dates:
        return None
    return await call_blocking(repository.load_potential_result, dates[0], semaphore=misc_semaphore)


async def list_potential_date_items(limit: int = 30) -> list[PotentialDateItem]:
    """列出可用结果日期与各自命中数量。"""
    summaries = await call_blocking(repository.list_potential_summaries, limit, semaphore=misc_semaphore)
    return [PotentialDateItem(date=date, count=count) for date, count in summaries]
