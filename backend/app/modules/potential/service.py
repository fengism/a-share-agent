"""每日潜力股挖掘编排：候选池 → 信号/质量/题材/基本面 → 风控与行业分散。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.financial_data.market.public import get_trading_calendar_view
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE
from app.financial_data.stock.public import (
    get_exchange_stock_master,
    get_historical_bars,
    get_spot_snapshot,
)
from app.modules.potential import constants
from app.modules.potential.fundamentals import _apply_fundamental_overlay
from app.modules.potential.persistence import repository
from app.modules.potential.regime import _combine_regime, _market_emotion, _resolve_market_regime
from app.modules.potential.schemas import (
    PotentialDailyResult,
    PotentialDateItem,
    PotentialRunStatus,
    PotentialStockItem,
)
from app.modules.potential.screening import _industry_stats, select_candidates
from app.modules.potential.signals import _evaluate_candidate
from app.modules.potential.themes import _load_theme_map
from app.modules.quant.public import CURATED_STRATEGY_KEYS, get_strategy_registry

logger = logging.getLogger(__name__)

_MAX_OUTPUT = constants._MAX_OUTPUT
_MAX_CONCURRENCY = constants._MAX_CONCURRENCY
_MAX_PER_INDUSTRY = constants._MAX_PER_INDUSTRY
_MAX_PER_UNCLASSIFIED = constants._MAX_PER_UNCLASSIFIED
_HISTORY_DAYS = constants._HISTORY_DAYS
_BAR_FETCH_TIMEOUT_SECONDS = constants._BAR_FETCH_TIMEOUT_SECONDS
_FUNDAMENTAL_CANDIDATE_LIMIT = constants._FUNDAMENTAL_CANDIDATE_LIMIT
_TRADING_CALENDAR_LOOKBACK_DAYS = constants._TRADING_CALENDAR_LOOKBACK_DAYS
_DAILY_MINING_CUTOFF = constants._DAILY_MINING_CUTOFF
_THEME_CONCEPT_LIMIT = constants._THEME_CONCEPT_LIMIT

_mining_singleflight: AsyncSingleFlight[PotentialDailyResult] = AsyncSingleFlight()

def _diversify_items(items: list[dict], max_output: int, max_per_industry: int) -> list[dict]:
    """按行业分散输出，避免榜单被单一热门行业占满。"""
    selected: list[dict] = []
    counts: dict[str, int] = {}
    for item in items:
        industry = item.get("industry") or "未分类"
        cap = _MAX_PER_UNCLASSIFIED if industry == "未分类" else max_per_industry
        if counts.get(industry, 0) >= cap:
            continue
        counts[industry] = counts.get(industry, 0) + 1
        selected.append(item)
        if len(selected) >= max_output:
            break
    return selected

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

async def mine_potential_stocks(
    market_date: date,
    spot_df: pd.DataFrame | None = None,
    master=None,
) -> PotentialDailyResult:
    """按指定交易日执行一轮挖掘：候选筛选 → 多策略信号 → 质量叠加 → 行业分散。"""
    if spot_df is None or master is None:
        fetched_spot, fetched_master = await asyncio.gather(
            get_spot_snapshot(),
            get_exchange_stock_master(),
        )
        spot_df = spot_df if spot_df is not None else fetched_spot
        master = master if master is not None else fetched_master
    master_records = master.records if master is not None else []

    candidates, industry_stats, emotion = await asyncio.gather(
        call_blocking(select_candidates, spot_df, master_records, semaphore=misc_semaphore),
        call_blocking(_industry_stats, spot_df, master_records, semaphore=misc_semaphore),
        call_blocking(_market_emotion, spot_df, master_records, semaphore=misc_semaphore),
    )
    for candidate in candidates:
        industry = candidate.get("industry")
        stats = industry_stats.get(industry) if isinstance(industry, str) else None
        candidate["sector_strength"] = stats["median_change_pct"] if stats else None
        candidate["theme_strength"] = 0.0
        candidate["themes"] = []

    (theme_map, hot_themes), (index_regime, regime_note) = await asyncio.gather(
        _load_theme_map({candidate["code"] for candidate in candidates}),
        _resolve_market_regime(market_date),
    )
    regime = _combine_regime(index_regime, emotion["label"])
    breadth_text = (
        f"上涨占比 {emotion['advance_ratio'] * 100:.0f}%"
        if emotion["advance_ratio"] is not None
        else "上涨占比未知"
    )
    regime_note = (
        f"{regime_note}；情绪 {emotion['label']}，{breadth_text}，"
        f"涨停 {emotion['limit_up_count']} 家 / 跌停 {emotion['limit_down_count']} 家"
    )
    for candidate in candidates:
        theme = theme_map.get(candidate["code"])
        if theme:
            candidate["theme_strength"] = theme["strength"]
            candidate["themes"] = theme["themes"]

    registry = get_strategy_registry()
    strategy_snapshots: dict = {}
    for key in sorted(CURATED_STRATEGY_KEYS):
        try:
            strategy_snapshots[key] = registry.resolve(key, None, {})
        except Exception as error:
            logger.warning("潜力股策略解析失败 key=%s: %s", key, error)

    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    start_date = market_date - timedelta(days=_HISTORY_DAYS)
    end_date = market_date
    items: list[dict] = []
    failed = 0
    market_date_text = market_date.isoformat()

    async def evaluate(candidate: dict) -> None:
        nonlocal failed
        code = candidate["code"]
        async with semaphore:
            try:
                bars = await asyncio.wait_for(
                    get_historical_bars(code, start_date, end_date, period="daily", adjust="qfq"),
                    timeout=_BAR_FETCH_TIMEOUT_SECONDS,
                )
            except Exception as error:
                failed += 1
                logger.debug("潜力股评估行情获取失败 %s: %s", code, error)
                return
            if not bars.items:
                failed += 1
                return
            last_bar_date = str(bars.items[-1].date)[:10]
            if last_bar_date != market_date_text:
                failed += 1
                logger.debug("潜力股跳过非目标交易日行情 %s: last_bar=%s", code, last_bar_date)
                return

        item = await call_blocking(
            _evaluate_candidate,
            bars.items,
            strategy_snapshots,
            candidate,
            regime,
            semaphore=misc_semaphore,
        )
        if item is not None:
            items.append(item)

    await asyncio.gather(*(evaluate(candidate) for candidate in candidates))
    fundamental_succeeded, fundamental_failed = await _apply_fundamental_overlay(items, market_date)
    logger.info(
        "潜力股基本面叠加完成: date=%s candidates=%s succeeded=%s failed=%s",
        market_date_text,
        min(len(items), _FUNDAMENTAL_CANDIDATE_LIMIT),
        fundamental_succeeded,
        fundamental_failed,
    )
    items.sort(key=lambda item: (-item["score"], -(item.get("amount") or 0)))
    selected = _diversify_items(items, _MAX_OUTPUT, _MAX_PER_INDUSTRY)

    return PotentialDailyResult(
        date=market_date_text,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        universe_size=len(candidates),
        evaluated=len(candidates) - failed,
        failed_count=failed,
        market_regime=regime,
        market_note=regime_note,
        market_emotion=emotion["label"],
        advance_ratio=emotion["advance_ratio"],
        limit_up_count=emotion["limit_up_count"],
        limit_down_count=emotion["limit_down_count"],
        median_change_pct=emotion["median_change_pct"],
        hot_themes=hot_themes,
        items=[PotentialStockItem(**item) for item in selected],
    )

async def _mine_and_save(market_date: date) -> PotentialDailyResult:
    """执行一轮完整挖掘并落盘；同一交易日的并发请求由 singleflight 合并。"""
    spot_df, master = await asyncio.gather(
        get_spot_snapshot(),
        get_exchange_stock_master(),
    )
    result = await mine_potential_stocks(market_date, spot_df=spot_df, master=master)
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

async def _load_saved_result(date_text: str) -> PotentialDailyResult | None:
    """读取已落盘的当日结果，统一收窄 call_blocking 的 Any 返回。"""
    loaded: PotentialDailyResult | None = await call_blocking(
        repository.load_potential_result, date_text, semaphore=misc_semaphore
    )
    return loaded

async def run_daily_mining(
    force: bool = False,
    now: datetime | None = None,
) -> PotentialDailyResult | None:
    """挖掘最近已收盘交易日；已有结果时跳过（force 可强制重跑）。

    同一交易日的并发触发通过 singleflight 合并，避免重复扫全市场、重复拉行情与财报。
    """
    local_now = _normalize_shanghai_now(now)
    market_date = await resolve_potential_market_date(local_now)
    if market_date is None:
        return None

    market_date_text = market_date.isoformat()
    if not force and repository.has_potential_result(market_date_text):
        return await _load_saved_result(market_date_text)
    if (
        local_now.weekday() < 5
        and local_now.time().replace(tzinfo=None) < _DAILY_MINING_CUTOFF
        and market_date != local_now.date()
    ):
        # 收盘前手动触发时，全市场快照仍是当日盘中数据，不能拿来挖上一交易日。
        logger.warning("收盘前跳过潜力股挖掘，避免使用盘中快照回挖上一交易日: date=%s", market_date_text)
        return await _load_saved_result(market_date_text)

    mined: PotentialDailyResult = await _mining_singleflight.do(
        market_date_text, lambda: _mine_and_save(market_date)
    )
    return mined

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
        return await _load_saved_result(date)
    dates = await call_blocking(repository.list_potential_dates, 1, semaphore=misc_semaphore)
    if not dates:
        return None
    return await _load_saved_result(dates[0])

async def list_potential_date_items(limit: int = 30) -> list[PotentialDateItem]:
    """列出可用结果日期与各自命中数量。"""
    summaries = await call_blocking(repository.list_potential_summaries, limit, semaphore=misc_semaphore)
    return [PotentialDateItem(date=date, count=count) for date, count in summaries]


_manual_run_task: asyncio.Task[None] | None = None
_manual_run_lock = asyncio.Lock()
_manual_run_state: dict[str, str | None] = {
    "status": "idle",
    "date": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def mining_run_status() -> PotentialRunStatus:
    """返回手动挖掘任务状态；running 以任务是否结束为准，避免状态残留。"""
    task = _manual_run_task
    running = task is not None and not task.done()
    return PotentialRunStatus(
        running=running,
        status="running" if running else str(_manual_run_state.get("status") or "idle"),
        date=_manual_run_state.get("date"),
        started_at=_manual_run_state.get("started_at"),
        finished_at=_manual_run_state.get("finished_at"),
        error=_manual_run_state.get("error"),
    )


async def start_daily_mining_background(force: bool = False) -> PotentialRunStatus:
    """后台启动一轮挖掘并立即返回；已有任务在跑时直接复用同一任务。"""
    global _manual_run_task
    async with _manual_run_lock:
        if _manual_run_task is not None and not _manual_run_task.done():
            return mining_run_status()
        _manual_run_state.update(
            status="running",
            date=None,
            started_at=_utc_now_text(),
            finished_at=None,
            error=None,
        )
        _manual_run_task = asyncio.create_task(_run_manual_mining(force))
        return mining_run_status()


async def _run_manual_mining(force: bool) -> None:
    try:
        result = await run_daily_mining(force=force)
    except asyncio.CancelledError:
        _manual_run_state.update(status="idle", finished_at=_utc_now_text(), error="cancelled")
        raise
    except Exception as error:  # noqa: BLE001 - 后台任务需记录失败并保留状态
        logger.warning("后台潜力股挖掘失败: %s", error, exc_info=True)
        _manual_run_state.update(status="failed", finished_at=_utc_now_text(), error=type(error).__name__)
        return
    _manual_run_state.update(
        status="completed",
        date=result.date if result is not None else None,
        finished_at=_utc_now_text(),
        error=None,
    )
