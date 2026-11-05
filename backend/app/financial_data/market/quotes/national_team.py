"""核心宽基 ETF 份额变化与国家队持仓代理监测。"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, TypeVar, cast

import pandas as pd

from app.core.cache import TTLCache, market_cache
from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore, misc_semaphore, tencent_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import safe_float
from app.core.timezones import SHANGHAI_TIMEZONE
from app.financial_data.market.quotes.index_kline import get_index_kline
from app.financial_data.market.quotes.national_team_aggregation import (
    build_national_team_response,
    build_support_backtest,
)
from app.financial_data.market.quotes.national_team_definitions import (
    ETF_POOL,
    INDEX_POOL,
    YI,
    IndexDefinition,
)
from app.financial_data.market.quotes.schemas import (
    NationalTeamIndexSeries,
    NationalTeamOverview,
    NationalTeamResponse,
    NationalTeamShareObservation,
    NationalTeamSupportBacktest,
)
from app.financial_data.market.trading_session import get_trading_calendar_view
from app.financial_data.stock.quotes.kline import get_kline
from app.infrastructure.persistence import national_team_etf_store
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_LEGACY_SNAPSHOT_PATH = Path(__file__).resolve().parents[4] / "data" / "national_team_etf" / "shares.json"

logger = logging.getLogger(__name__)

_SZSE_MAX_WINDOW_DAYS = 7
_SZSE_MAX_WINDOWS_PER_REFRESH = 8
_SSE_MAX_DATES_PER_REFRESH = 4
_SZSE_REQUEST_INTERVAL_SECONDS = 0.15
_REFRESH_TIMEOUT_SECONDS = 35.0
# 优先腾讯财经极速日K；若需回退TDX排队或重试，120s/45s 充足预算避免无谓超时截断
_PRICE_TIMEOUT_SECONDS = 120.0
_PRICE_ITEM_TIMEOUT_SECONDS = 45.0
_SOURCE_TIMEOUT_SECONDS = 20.0
_price_semaphore = asyncio.Semaphore(8)
_source_limits = {
    "sse": asyncio.Semaphore(2),
    "szse_history": asyncio.Semaphore(1),
    "szse_current": asyncio.Semaphore(1),
    "sse_current": asyncio.Semaphore(1),
}
_source_cache = TTLCache(maxsize=1024, name="national_team_sources")
_source_cooldowns = TTLCache(maxsize=8, name="national_team_cooldowns")
_source_flight = AsyncSingleFlight[object]()
_response_flight = AsyncSingleFlight[NationalTeamResponse]()
_stale_responses = TTLCache(maxsize=64, name="national_team_stale")
_refresh_cooldowns = TTLCache(maxsize=64, name="national_team_refresh_cooldown")
_refresh_tasks: dict[str, asyncio.Task] = {}
_active_tasks: set[asyncio.Task] = set()
_stopping = False
T = TypeVar("T")

#: 收盘后自动刷新使用的默认窗口，与前端默认的 120 天保持一致。
_DEFAULT_REFRESH_DAYS = 120
#: 回测缓存前缀：评分落库后按前缀失效，避免把旧样本的结论继续发出去。
_BACKTEST_CACHE_PREFIX = "national_team_backtest:"
#: 自动刷新只看收盘后这段时间，避免全天候选上游叠加压力。
_AFTER_CLOSE_START_HOUR = 16
_AFTER_CLOSE_END_HOUR = 18


# ---------------------------------------------------------------------------
# 观测数据
#
# 国家队页面的刷新质量无从从外部观察：数据缺失了、上游挂了、覆盖率下降都在日志里
# 混在其他请求中间。这里记录一份进程内计数，由 /metrics 导出（见 app/core/prometheus.py）。
# ---------------------------------------------------------------------------
_metrics_lock = threading.Lock()
_refresh_metrics: dict[str, object] = {
    "attempts_total": 0,
    "failures_total": 0,
    "last_duration_ms": 0.0,
    "last_success_timestamp": 0.0,
    "last_error": "",
    "last_trigger": "",
    "by_trigger": {},
    "source_failures": {},
    "coverage_ratio": 0.0,
    "partial": 0,
    "covered_etf_count": 0,
    "total_etf_count": 0,
    "as_of_date": "",
    "stale": 0,
    "scheduled_business_date": "",
    "scheduled_completed_date": "",
}


def national_team_snapshot() -> dict[str, object]:
    """返回国家队刷新与数据质量的当前快照，供 Prometheus 导出。"""
    with _metrics_lock:
        return {
            **{key: value for key, value in _refresh_metrics.items() if key not in {"by_trigger", "source_failures"}},
            "by_trigger": {
                trigger: dict(counts)
                for trigger, counts in cast(dict, _refresh_metrics["by_trigger"]).items()
            },
            "source_failures": dict(cast(dict, _refresh_metrics["source_failures"])),
        }


def _record_source_failure(scope: str) -> None:
    with _metrics_lock:
        failures = cast(dict[str, int], _refresh_metrics["source_failures"])
        failures[scope] = failures.get(scope, 0) + 1


def _record_collection(
    trigger: str,
    *,
    started: float,
    response: NationalTeamResponse | None = None,
    error: BaseException | None = None,
) -> None:
    """记录一次完整采集的成败与数据质量。"""
    duration_ms = round((time.monotonic() - started) * 1000, 2)
    with _metrics_lock:
        _refresh_metrics["attempts_total"] = int(_refresh_metrics["attempts_total"]) + 1
        _refresh_metrics["last_duration_ms"] = duration_ms
        _refresh_metrics["last_trigger"] = trigger
        by_trigger = cast(dict[str, dict[str, int]], _refresh_metrics["by_trigger"])
        counts = by_trigger.setdefault(trigger, {"attempts": 0, "failures": 0})
        counts["attempts"] += 1
        if error is not None:
            _refresh_metrics["failures_total"] = int(_refresh_metrics["failures_total"]) + 1
            counts["failures"] += 1
            # 只保留异常类名：完整消息可能带 URL、参数等内部细节。
            _refresh_metrics["last_error"] = type(error).__name__
            return
        if response is None:
            return
        _refresh_metrics["last_error"] = ""
        _refresh_metrics["last_success_timestamp"] = time.time()
        _refresh_metrics["coverage_ratio"] = response.summary.coverage_ratio
        _refresh_metrics["partial"] = int(response.partial)
        _refresh_metrics["stale"] = int(response.stale)
        _refresh_metrics["covered_etf_count"] = response.covered_etf_count
        _refresh_metrics["total_etf_count"] = response.total_etf_count
        _refresh_metrics["as_of_date"] = response.as_of_date or ""


def _calendar_window(moment: datetime) -> tuple[date, bool]:
    local = moment.astimezone(SHANGHAI_TIMEZONE)
    return local.date(), local.hour >= 16


def _response_cache_key(days: int, now: datetime | None = None) -> str:
    day, released = _calendar_window(now or datetime.now(UTC))
    return f"national_team_etf_v4:{days}:{day.isoformat()}:{int(released)}"


async def _source_request(scope: str, key: str, loader: Callable[[], Awaitable[T]]) -> T:
    if _stopping:
        raise asyncio.CancelledError
    cache_key = f"{scope}:{key}"

    async def load() -> T:
        task = asyncio.current_task()
        _active_tasks.add(task)
        try:
            cached = _source_cache.get(cache_key)
            if cached is not None:
                return cast(T, cached)
            if _source_cooldowns.get(scope):
                raise UpstreamUnavailableError(f"{scope} 数据源冷却中")
            upstream_started = False
            try:
                async with asyncio.timeout(_SOURCE_TIMEOUT_SECONDS), _source_limits[scope]:
                    # 排队期间其他请求可能失败；获得容量后仍需检查冷却。
                    if _source_cooldowns.get(scope):
                        raise UpstreamUnavailableError(f"{scope} 数据源冷却中")
                    upstream_started = True
                    result = await loader()
            except Exception:
                # 本地拥塞不是上游故障；冷却拒绝也不能续期，避免持续请求阻止恢复。
                if upstream_started:
                    _source_cooldowns.set(scope, True, ttl=10)
                    _record_source_failure(scope)
                raise
            _source_cache.set(cache_key, result, ttl=60)
            return result
        finally:
            _active_tasks.discard(task)

    return cast(T, await _source_flight.do(cache_key, load))


def initialize_national_team_refresh() -> None:
    """允许同一进程重新进入应用生命周期；只在完成关闭后重建循环绑定对象。"""
    global _stopping, _source_flight, _response_flight, _source_limits, _price_semaphore
    if not _stopping:
        return
    _source_flight = AsyncSingleFlight()
    _response_flight = AsyncSingleFlight()
    _source_limits = {
        "sse": asyncio.Semaphore(2),
        "szse_history": asyncio.Semaphore(1),
        "szse_current": asyncio.Semaphore(1),
        "sse_current": asyncio.Semaphore(1),
    }
    _price_semaphore = asyncio.Semaphore(4)
    _active_tasks.clear()
    _refresh_cooldowns.clear()
    _source_cooldowns.clear()
    with _metrics_lock:
        _refresh_metrics["scheduled_business_date"] = ""
        _refresh_metrics["scheduled_completed_date"] = ""
    _stopping = False


async def shutdown_national_team_refresh() -> None:
    global _stopping
    _stopping = True
    # 让刚创建的 singleflight loader 注册自身后再统一取消。
    await asyncio.sleep(0)
    tasks = set(_refresh_tasks.values()) | _active_tasks
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _refresh_tasks.clear()


def _support_score_rows(
    response: NationalTeamResponse,
) -> list[tuple[str, float, str, float, float, float | None]]:
    """把响应里的评分历史与当日沪深300 收盘配成待落库的行。"""
    csi300 = next((item for item in response.indices if item.index_key == "csi300"), None)
    closes = {point.date: point.index_close for point in csi300.points} if csi300 else {}
    return [
        (
            point.date,
            point.score,
            point.status,
            point.confidence,
            point.coverage_ratio,
            closes.get(point.date),
        )
        for point in response.support_score_history
    ]


async def _record_support_scores(response: NationalTeamResponse) -> None:
    """落库失败不能影响采集结果，只记一条警告。"""
    rows = _support_score_rows(response)
    if not rows:
        return
    try:
        # 落库是增强信息，不能因为 DB 锁竞争把采集响应一起拖住。
        await asyncio.wait_for(
            call_blocking(
                lambda: national_team_etf_store.save_support_scores(rows),
                semaphore=misc_semaphore,
            ),
            timeout=2.0,
        )
    except Exception as error:
        logger.warning("国家队评分快照写入失败 error=%r", error)
        return
    # 样本变了，之前缓存的回测结论就不再代表最新状态。
    market_cache.delete_prefix(_BACKTEST_CACHE_PREFIX)


async def get_national_team_backtest(days: int = 365) -> NationalTeamSupportBacktest:
    """读取已落库的评分，计算信号后 5/20 日表现。"""
    window = max(30, min(days, 1095))
    cache_key = f"{_BACKTEST_CACHE_PREFIX}{window}"
    cached = market_cache.get(cache_key)
    if cached is not None:
        return NationalTeamSupportBacktest.model_validate(cached)
    rows = await call_blocking(
        lambda: national_team_etf_store.load_support_scores(limit=window),
        semaphore=misc_semaphore,
    )
    result = build_support_backtest(rows, window_samples=window)
    market_cache.set(cache_key, result, ttl=300)
    return result


def _read_snapshot(
    codes: set[str] | None = None,
) -> tuple[dict[str, dict[str, float]], set[str], set[str]]:
    """从 market_data.db 读取 ETF 份额与已检查交易日。

    Returns:
        (share_history, checked_sse_dates, checked_szse_dates)。
    """
    target_codes = codes or set(ETF_POOL)
    national_team_etf_store.import_legacy_snapshot(_LEGACY_SNAPSHOT_PATH, allowed_codes=set(ETF_POOL))
    share_history = national_team_etf_store.load_share_history(
        sorted(code for code in target_codes if code in ETF_POOL),
        verified_only=True,
    )
    checked_sse = national_team_etf_store.load_checked_dates("sse")
    checked_szse = national_team_etf_store.load_checked_dates("szse")
    return share_history, checked_sse, checked_szse


def _write_snapshot(
    share_history: dict[str, dict[str, float]],
    checked_sse_dates: set[str],
    checked_szse_dates: set[str],
) -> None:
    """将内存中的 ETF 份额与回填状态持久化到 market_data.db。

    Args:
        share_history: {code: {date: shares}}。
        checked_sse_dates: 上交所已检查日期。
        checked_szse_dates: 深交所已检查日期。
    """
    national_team_etf_store.save_snapshot(
        {
            source: [
                (code, point_date, shares)
                for code, definition in ETF_POOL.items()
                if definition.exchange == exchange
                for point_date, shares in share_history.get(code, {}).items()
            ]
            for exchange, source in (("SH", "sse_history"), ("SZ", "szse_history"))
        },
        checked_sse_dates,
        checked_szse_dates,
    )


async def _fetch_sse_date(point_date: str) -> tuple[str, dict[str, float]]:
    values = await provider_gateway.call(
        "exchange",
        "fetch_sse_etf_shares",
        lambda: get_provider("exchange").fetch_sse_etf_shares(point_date),
        retry_budget_seconds=_SOURCE_TIMEOUT_SECONDS,
    )
    return point_date, {
        code: shares for code, shares in values.items() if code in ETF_POOL and ETF_POOL[code].exchange == "SH"
    }


async def _backfill_sse_history(
    share_history: dict[str, dict[str, float]],
    checked_dates: set[str],
    trading_dates: list[str],
) -> bool:
    sh_codes = {code for code, item in ETF_POOL.items() if item.exchange == "SH"}
    missing_dates = [
        point_date
        for point_date in trading_dates
        if point_date not in checked_dates or not all(point_date in share_history.get(code, {}) for code in sh_codes)
    ]
    if not missing_dates:
        return False
    semaphore = asyncio.Semaphore(2)
    changed = False

    def merge(point_date: str, values: dict[str, float]) -> None:
        nonlocal changed
        for code, shares in values.items():
            if code in sh_codes and share_history.get(code, {}).get(point_date) != shares:
                share_history.setdefault(code, {})[point_date] = shares
                changed = True
        if all(point_date in share_history.get(code, {}) for code in sh_codes):
            changed = changed or point_date not in checked_dates
            checked_dates.add(point_date)

    async def fetch(point_date: str) -> None:
        nonlocal changed
        async with semaphore:
            try:

                async def load():
                    return await _fetch_sse_date(point_date)

                _, values = await _source_request("sse", point_date, load)
            except Exception as error:
                logger.warning("上交所 ETF 份额获取失败 date=%s error=%r", point_date, error)
                return
        merge(point_date, values)

    target_dates = list(reversed(missing_dates))[:_SSE_MAX_DATES_PER_REFRESH]
    tasks = [asyncio.create_task(fetch(day)) for day in target_dates]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # 共享请求已完成但结果尚未交付等待方时，取消也不能丢失进度。
        for day in target_dates:
            cached = _source_cache.get(f"sse:{day}")
            if cached is not None:
                merge(day, cached[1])
    return changed


async def _fetch_szse_history_with_retry(
    start_date: str,
    end_date: str,
) -> tuple[dict[str, dict[str, float]], set[str]]:
    # 重试只由 gateway 执行；外层仍保留源级超时、冷却和 singleflight。
    history, _ = await provider_gateway.call(
        "exchange",
        "fetch_szse_etf_share_history",
        lambda: get_provider("exchange").fetch_szse_etf_share_history(start_date, end_date),
        max_attempts=3,
        retry_budget_seconds=_SOURCE_TIMEOUT_SECONDS,
    )
    history = {code: points for code, points in history.items() if code in ETF_POOL and ETF_POOL[code].exchange == "SZ"}
    return history, {day for points in history.values() for day in points}


def _szse_date_ranges(missing_dates: list[str]) -> list[tuple[str, str]]:
    """按至多 7 个自然日切段，并优先返回最近区间。"""
    if not missing_dates:
        return []
    ordered_dates = sorted(set(missing_dates))
    ranges: list[tuple[str, str]] = []
    range_start = ordered_dates[0]
    previous = ordered_dates[0]
    for point_date in ordered_dates[1:]:
        span_days = (date.fromisoformat(point_date) - date.fromisoformat(range_start)).days + 1
        if span_days > _SZSE_MAX_WINDOW_DAYS:
            ranges.append((range_start, previous))
            range_start = point_date
        previous = point_date
    ranges.append((range_start, previous))
    return list(reversed(ranges))


async def _backfill_szse_history(
    share_history: dict[str, dict[str, float]],
    checked_dates: set[str],
    trading_dates: list[str],
) -> bool:
    sz_codes = {code for code, item in ETF_POOL.items() if item.exchange == "SZ"}
    missing_dates = [
        day
        for day in trading_dates
        if day not in checked_dates or not all(day in share_history.get(code, {}) for code in sz_codes)
    ]
    changed = False
    ranges = _szse_date_ranges(missing_dates)[:_SZSE_MAX_WINDOWS_PER_REFRESH]

    def merge(range_start: str, range_end: str, history: dict[str, dict[str, float]], returned_dates: set[str]) -> None:
        nonlocal changed
        for code, values in history.items():
            if code not in sz_codes:
                continue
            target = share_history.setdefault(code, {})
            for point_date, shares in values.items():
                if range_start <= point_date <= range_end and target.get(point_date) != shares:
                    target[point_date] = shares
                    changed = True
        new_checked = {
            day
            for day in returned_dates.intersection(missing_dates)
            if all(day in share_history.get(code, {}) for code in sz_codes)
        }
        if not new_checked.issubset(checked_dates):
            checked_dates.update(new_checked)
            changed = True

    for range_index, (range_start, range_end) in enumerate(ranges):
        key = f"{range_start}:{range_end}"
        try:
            history, returned_dates = await _source_request(
                "szse_history",
                key,
                lambda start=range_start, end=range_end: _fetch_szse_history_with_retry(
                    start.replace("-", ""), end.replace("-", "")
                ),
            )
            merge(range_start, range_end, history, returned_dates)
        except Exception as error:
            logger.warning("深交所 ETF 历史份额获取失败 start=%s end=%s error=%r", range_start, range_end, error)
            break  # 源级冷却，避免继续请求同源旧窗口并重复输出警告。
        finally:
            cached = _source_cache.get(f"szse_history:{key}")
            if cached is not None:
                merge(range_start, range_end, *cached)
        if range_index < len(ranges) - 1:
            await asyncio.sleep(_SZSE_REQUEST_INTERVAL_SECONDS)
    return changed


async def _fetch_szse_current_direct() -> dict[str, float]:
    return await provider_gateway.call(
        "exchange",
        "fetch_szse_etf_current_shares",
        lambda: get_provider("exchange").fetch_szse_etf_current_shares(),
        max_attempts=1,
    )


async def _fetch_szse_current_eastmoney(missing_codes: set[str]) -> dict[str, float]:
    if not missing_codes:
        return {}
    return await provider_gateway.call_blocking(
        "eastmoney",
        "fetch_etf_current_shares",
        get_provider("eastmoney").fetch_etf_current_shares,
        missing_codes,
        semaphore=eastmoney_semaphore,
        is_fallback_attempt=True,
        max_attempts=1,
    )


async def _fetch_szse_current() -> dict[str, NationalTeamShareObservation]:
    target_codes = {code for code, item in ETF_POOL.items() if item.exchange == "SZ"}
    result: dict[str, NationalTeamShareObservation] = {}

    def merge(values: dict[str, float], source: str) -> None:
        fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
        for code, shares in values.items():
            if code in target_codes:
                result[code] = NationalTeamShareObservation(
                    code=code,
                    source=source,
                    shares_100m=shares / YI,
                    fetched_at=fetched_at,
                )

    try:
        async with asyncio.timeout(5.0):
            merge(await _fetch_szse_current_direct(), "szse_current")
    except Exception as error:
        logger.warning("深交所 ETF 当前份额直连失败 error=%r", error)

    missing_codes = target_codes.difference(result)
    if missing_codes:
        try:
            async with asyncio.timeout(5.0):
                merge(await _fetch_szse_current_eastmoney(missing_codes), "eastmoney_current")
        except Exception as error:
            logger.warning("深交所 ETF 当前份额东财备选数据源失败 error=%r", error)
    if not result:
        raise UpstreamUnavailableError("深交所 ETF 当前份额所有数据源均不可用")
    return result


async def _fetch_sse_current_eastmoney(missing_codes: set[str]) -> dict[str, float]:
    if not missing_codes:
        return {}
    return await provider_gateway.call_blocking(
        "eastmoney",
        "fetch_etf_current_shares",
        get_provider("eastmoney").fetch_etf_current_shares,
        missing_codes,
        semaphore=eastmoney_semaphore,
        is_fallback_attempt=True,
        max_attempts=1,
    )


async def _fetch_sse_current() -> dict[str, NationalTeamShareObservation]:
    target_codes = {code for code, item in ETF_POOL.items() if item.exchange == "SH"}
    result: dict[str, NationalTeamShareObservation] = {}
    try:
        async with asyncio.timeout(6.0):
            values = await _fetch_sse_current_eastmoney(target_codes)
            fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
            for code, shares in values.items():
                if code in target_codes:
                    result[code] = NationalTeamShareObservation(
                        code=code,
                        source="eastmoney_current",
                        shares_100m=shares / YI,
                        fetched_at=fetched_at,
                    )
    except Exception as error:
        logger.warning("上交所 ETF 当前份额东财备选数据源失败 error=%r", error)
    if not result:
        raise UpstreamUnavailableError("上交所 ETF 当前份额备选数据源不可用")
    return result


def _write_observations(values: dict[str, NationalTeamShareObservation]) -> None:
    national_team_etf_store.save_observations(
        (point.code, point.source, point.shares_100m * YI, datetime.fromisoformat(point.fetched_at).timestamp())
        for point in values.values()
    )


def _read_provenance() -> tuple[dict[str, dict[str, dict]], list[NationalTeamShareObservation]]:
    observations = [
        NationalTeamShareObservation(
            code=row["code"],
            source=row["source"],
            shares_100m=row["shares"] / YI,
            fetched_at=datetime.fromtimestamp(row["fetched_at"], UTC).isoformat(timespec="seconds"),
        )
        for row in national_team_etf_store.load_observations(ETF_POOL)
        if row["fetched_at"] >= datetime.now(UTC).timestamp() - 86400
    ]
    return national_team_etf_store.load_share_metadata(ETF_POOL), observations


async def _load_etf_market_history(
    code: str,
    start_date: str,
    end_date: str,
) -> tuple[dict[str, float], dict[str, float]]:
    """优先从腾讯财经拉取 ETF 收盘价与成交额（轻量快速且无单线程互斥锁），失败时平滑回退 get_kline。"""
    try:
        provider = get_provider("tencent")
        frame = await call_blocking(
            provider.fetch_stock_kline,
            code,
            start_date,
            end_date,
            "",
            semaphore=tencent_semaphore,
        )
        if isinstance(frame, pd.DataFrame) and not frame.empty and "日期" in frame.columns and "收盘" in frame.columns:
            closes: dict[str, float] = {}
            amounts_100m: dict[str, float] = {}
            for _, row in frame.iterrows():
                raw_date = row.get("日期")
                close_val = safe_float(row.get("收盘"))
                amt_val = safe_float(row.get("成交额"))
                if raw_date is not None and close_val is not None:
                    parsed = pd.to_datetime(raw_date, errors="coerce")
                    if pd.notna(parsed):
                        day_str = parsed.strftime("%Y-%m-%d")
                        closes[day_str] = close_val
                        if amt_val is not None:
                            amounts_100m[day_str] = round(amt_val / YI, 4)
            if closes:
                return closes, amounts_100m
    except Exception as error:
        logger.debug("腾讯财经获取 ETF %s 行情失败，回退 get_kline: %r", code, error)

    data = await get_kline(
        code,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="",
        max_provider_sources=2,
    )
    closes = {item.date: item.close for item in data.items}
    amounts_100m = {item.date: round(item.amount / YI, 4) for item in data.items if item.amount is not None}
    return closes, amounts_100m


async def _load_etf_close_history(
    code: str,
    start_date: str,
    end_date: str,
) -> dict[str, float]:
    """优先从腾讯财经拉取 ETF 收盘价，失败时平滑回退 get_kline。"""
    closes, _ = await _load_etf_market_history(code, start_date, end_date)
    return closes


async def _load_index_close_history(
    key: str,
    definition: IndexDefinition,
    start_date: str,
    end_date: str,
) -> dict[str, float]:
    """优先从腾讯财经拉取核心指数收盘价（极速且无单线程互斥锁），失败时平滑回退 get_index_kline。"""
    try:
        provider = get_provider("tencent")
        frame = await call_blocking(
            provider.fetch_index_kline,
            definition.index_code,
            start_date,
            end_date,
            semaphore=tencent_semaphore,
        )
        if isinstance(frame, pd.DataFrame) and not frame.empty and "日期" in frame.columns and "收盘" in frame.columns:
            closes: dict[str, float] = {}
            for _, row in frame.iterrows():
                raw_date = row.get("日期")
                close_val = safe_float(row.get("收盘"))
                if raw_date is not None and close_val is not None:
                    parsed = pd.to_datetime(raw_date, errors="coerce")
                    if pd.notna(parsed):
                        closes[parsed.strftime("%Y-%m-%d")] = close_val
            if closes:
                return closes
    except Exception as error:
        logger.debug("腾讯财经获取指数 %s 行情失败，回退 get_index_kline: %r", key, error)

    symbol = definition.index_code.split(".")[0]
    data = await get_index_kline(symbol, "daily", start_date, end_date)
    return {item.date: item.close for item in data.items}


async def _load_price_history(
    start_date: str,
    end_date: str,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    etf_history: dict[str, dict[str, float]] = {}
    etf_amount_history: dict[str, dict[str, float]] = {}
    index_history: dict[str, dict[str, float]] = {}

    async def load_etf(code: str) -> tuple[str, dict[str, float], dict[str, float]]:
        try:
            async with _price_semaphore:
                async with asyncio.timeout(_PRICE_ITEM_TIMEOUT_SECONDS):
                    closes, amounts = await _load_etf_market_history(code, start_date, end_date)
                    etf_history[code] = closes
                    etf_amount_history[code] = amounts
                    return code, closes, amounts
        except Exception as error:
            logger.warning("国家队 ETF 行情获取失败 code=%s error=%r", code, error)
            return code, {}, {}

    async def load_index(key: str, definition: IndexDefinition) -> tuple[str, dict[str, float]]:
        try:
            async with _price_semaphore:
                async with asyncio.timeout(_PRICE_ITEM_TIMEOUT_SECONDS):
                    closes = await _load_index_close_history(key, definition, start_date, end_date)
                    index_history[key] = closes
                    return key, closes
        except Exception as error:
            logger.warning("国家队指数行情获取失败 index=%s error=%r", key, error)
            return key, {}

    # 优先加载核心指数行情，确保大盘基准与走势图完整呈现；随后加载 ETF 行情
    index_tasks = [asyncio.create_task(load_index(key, definition)) for key, definition in INDEX_POOL.items()]
    etf_tasks = [asyncio.create_task(load_etf(code)) for code in ETF_POOL]
    all_tasks = index_tasks + etf_tasks
    try:
        async with asyncio.timeout(_PRICE_TIMEOUT_SECONDS):
            await asyncio.gather(*all_tasks)
    except TimeoutError:
        logger.warning("国家队行情获取超时，保留已完成结果 etfs=%s indices=%s", len(etf_history), len(index_history))
    finally:
        for task in all_tasks:
            task.cancel()
        await asyncio.gather(*all_tasks, return_exceptions=True)
    return etf_history, index_history, etf_amount_history


async def _refresh_exchange(
    exchange: Literal["SH", "SZ"],
    share_history: dict[str, dict[str, float]],
    checked_dates: set[str],
    trading_dates: list[str],
) -> None:
    codes = {code for code, item in ETF_POOL.items() if item.exchange == exchange}
    before = {code: dict(share_history.get(code, {})) for code in codes}
    checked_before = set(checked_dates)

    async def history() -> None:
        try:
            async with asyncio.timeout(_REFRESH_TIMEOUT_SECONDS):
                if exchange == "SH":
                    await _backfill_sse_history(share_history, checked_dates, trading_dates)
                else:
                    await _backfill_szse_history(share_history, checked_dates, trading_dates)
        except Exception as error:
            logger.warning("国家队历史份额刷新失败 exchange=%s error=%r，使用存量数据", exchange, error)

    async def current() -> None:
        now = datetime.now(SHANGHAI_TIMEZONE)
        latest = trading_dates[-1] if trading_dates else None
        if latest != now.date().isoformat() or now.hour < 16:
            return
        missing = {code for code in codes if latest not in share_history.get(code, {})}
        if not missing:
            return
        try:
            async with asyncio.timeout(12.0):
                if exchange == "SZ":
                    values = await _source_request("szse_current", latest, _fetch_szse_current)
                else:
                    values = await _source_request("sse_current", latest, _fetch_sse_current)
            # 没有业务日期的当前快照只能作为独立观察，不进入历史或回填完成标记。
            await call_blocking(_write_observations, values, semaphore=misc_semaphore)
        except Exception as error:
            logger.warning("国家队当前份额刷新失败 exchange=%s error=%r", exchange, error)

    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(history())
            group.create_task(current())
    finally:
        # 即使某源超时或请求被取消，也保存已经完成的增量，不重写旧行。
        delta = {
            code: {
                day: shares for day, shares in share_history.get(code, {}).items() if before[code].get(day) != shares
            }
            for code in codes
        }
        delta = {code: values for code, values in delta.items() if values}
        new_checked = checked_dates - checked_before
        if delta or new_checked:
            save_task = asyncio.create_task(
                call_blocking(
                    _write_snapshot,
                    delta,
                    new_checked if exchange == "SH" else set(),
                    new_checked if exchange == "SZ" else set(),
                    semaphore=misc_semaphore,
                )
            )
            try:
                await asyncio.shield(save_task)
            except asyncio.CancelledError:
                await save_task
                raise


async def _load_expected_trading_dates(start: date, now: datetime) -> tuple[list[str], bool]:
    # 当日份额给予收盘后发布宽限；盘中按上一交易日检查新鲜度。
    end = now.date() if now.hour >= 16 else now.date() - timedelta(days=1)
    try:
        async with asyncio.timeout(3.0):
            calendar = await get_trading_calendar_view(start, end)
        if calendar.trade_dates:
            return calendar.trade_dates, calendar.degraded
    except Exception as error:
        logger.warning("国家队交易日历获取失败 error=%r", error)
    return [], True


def _response_window(days: int, now: datetime) -> tuple[date, date]:
    """计算监测视图的起止日期；行情缓存键依赖该窗口，预热必须复用同一计算。"""
    end = now.date()
    return end - timedelta(days=days - 1), end


def without_etf_points(response: NationalTeamResponse) -> NationalTeamResponse:
    """去掉每只 ETF 的点位序列，约省 65% 响应体积。

    前端 ETF 表格与 CSV 只需要最新一天的标量（已由
    ``latest_estimated_net_flow_100m`` 提供），22 只 × N 天的 ``points``
    全部传输、全部 JSON 解析，但只用最后一个元素。

    **缓存里存完整响应**，裁剪只在序列化前做：否则 ``include_etf_points``
    的两个取值会分裂成两份缓存，容量翻倍且互相抢占。
    """
    trimmed = response.model_copy(deep=False)
    trimmed.etfs = [item.model_copy(update={"points": []}) for item in response.etfs]
    trimmed.etf_points_included = False
    return trimmed


def without_index_points(response: NationalTeamResponse) -> NationalTeamResponse:
    """去掉指数点位序列，保留最新标量，供首屏先渲染表格与结论。

    指数点位是详情页 10 张图的主要体积来源；前端先拿到标量与资金流，再单独拉
    ``/national-team/index-series`` 填充图表。
    """
    trimmed = response.model_copy(deep=False)
    trimmed.indices = [item.model_copy(update={"points": []}) for item in response.indices]
    trimmed.index_points_included = False
    return trimmed


def without_flow_breakdown(response: NationalTeamResponse) -> NationalTeamResponse:
    """去掉按宽基拆分的当日资金流，保留总量与分类拆分。

    前端图表只用 ``flows_by_category``；``flows_by_index`` 与指数序列信息重复。
    """
    trimmed = response.model_copy(deep=False)
    trimmed.daily_flows = [
        item.model_copy(update={"flows_by_index": {}}) for item in response.daily_flows
    ]
    trimmed.flow_breakdown_included = False
    return trimmed


async def _collect_response(days: int = 120, *, trigger: str = "request", force: bool = False) -> NationalTeamResponse:
    """返回核心宽基 ETF 份额与指数价格的国家队代理监测视图。

    Param:
        days: 监测窗口自然日数，会被裁剪到 30–365。
        trigger: 采集来源（``request`` / ``scheduled`` / ``prewarm``），只用于指标分维。
        force: 为真时跳过响应缓存，仍写入。定时刷新必须越过缓存，否则会拿回
            ``partial`` 时写入的 60s 旧值，刷新等于没刷。
    """
    days = max(30, min(days, 365))
    now = datetime.now(SHANGHAI_TIMEZONE)
    cache_key = _response_cache_key(days, now)
    if not force:
        cached = market_cache.get(cache_key)
        if cached is not None:
            return NationalTeamResponse.model_validate(cached)

    started = time.monotonic()
    try:
        result = await _collect_response_uncached(days, now=now, cache_key=cache_key)
    except asyncio.CancelledError:
        # 关闭时的取消不是刷新失败，计进 failures 会误导读数。
        raise
    except BaseException as error:
        _record_collection(trigger, started=started, error=error)
        raise
    _record_collection(trigger, started=started, response=result)
    await _record_support_scores(result)
    return result


async def _collect_response_uncached(
    days: int,
    *,
    now: datetime,
    cache_key: str,
) -> NationalTeamResponse:
    start, end = _response_window(days, now)
    (expected_trading_dates, calendar_degraded), (etf_closes, index_closes, etf_amounts) = await asyncio.gather(
        _load_expected_trading_dates(start, now),
        _load_price_history(start.strftime("%Y%m%d"), end.strftime("%Y%m%d")),
    )

    start_iso, end_iso = start.isoformat(), end.isoformat()
    etf_closes, index_closes, etf_amounts = (
        {
            key: {day: value for day, value in values.items() if start_iso <= day <= end_iso}
            for key, values in history.items()
        }
        for history in (etf_closes, index_closes, etf_amounts)
    )
    # 单个指数行情可能滞后；使用所有行情源的日期，避免漏补最新交易日。
    trading_dates = sorted(
        {day for history in (etf_closes, index_closes) for values in history.values() for day in values}
        | set(expected_trading_dates)
    )

    share_history, checked_sse_dates, checked_szse_dates = await call_blocking(
        _read_snapshot,
        semaphore=misc_semaphore,
    )

    async with asyncio.TaskGroup() as group:
        group.create_task(_refresh_exchange("SH", share_history, checked_sse_dates, trading_dates))
        group.create_task(_refresh_exchange("SZ", share_history, checked_szse_dates, trading_dates))
    if not any(share_history.get(code) for code in ETF_POOL):
        raise UpstreamUnavailableError("ETF 份额数据上游暂时不可用")

    filtered_shares = {
        code: {point_date: value for point_date, value in values.items() if start_iso <= point_date <= end_iso}
        for code, values in share_history.items()
    }
    metadata, observations = await call_blocking(_read_provenance, semaphore=misc_semaphore)
    finished_at = datetime.now(UTC)
    result = build_national_team_response(
        share_history=filtered_shares,
        share_metadata=metadata,
        observations=observations,
        etf_close_history=etf_closes,
        index_close_history=index_closes,
        etf_amount_history=etf_amounts,
        fetched_at=finished_at.isoformat(timespec="seconds"),
        requested_days=days,
        expected_trading_dates=expected_trading_dates,
        calendar_degraded=calendar_degraded,
    )
    if _calendar_window(now) != _calendar_window(finished_at):
        # 请求本身跨过发布窗口时，开始时加载的日历也已失效。
        result = result.model_copy(update={"partial": True, "calendar_degraded": True, "expected_date": None})
    _stale_responses.set(str(days), result, ttl=3600)
    market_cache.set(cache_key, result, ttl=60 if result.partial else 900)
    return result


async def _shared_response(days: int, *, trigger: str = "request", force: bool = False) -> NationalTeamResponse:
    if _stopping:
        raise asyncio.CancelledError

    async def load() -> NationalTeamResponse:
        task = asyncio.current_task()
        _active_tasks.add(task)
        try:
            return await _collect_response(days, trigger=trigger, force=force)
        finally:
            _active_tasks.discard(task)

    if force:
        # 强制刷新不能走 singleflight 的缓存位，否则会拿回同一个未刷新的飞行结果。
        return await load()
    return await _response_flight.do(_response_cache_key(days), load)


def _start_refresh(days: int) -> None:
    key = str(days)
    if _stopping or key in _refresh_tasks or _refresh_cooldowns.get(key):
        return

    async def refresh() -> None:
        try:
            await _shared_response(days)
        except Exception as error:
            _refresh_cooldowns.set(key, True, ttl=60)
            logger.warning("国家队后台刷新失败 days=%s error=%r", days, error)
        finally:
            _refresh_tasks.pop(key, None)

    _refresh_tasks[key] = asyncio.create_task(refresh(), name=f"national-team-refresh-{days}")


async def get_national_team_etf_holdings(
    days: int = 120,
    *,
    include_etf_points: bool = True,
    include_index_points: bool = True,
    include_flow_breakdown: bool = True,
) -> NationalTeamResponse:
    """返回国家队代理监测视图。

    Param:
        days: 监测窗口自然日数，会被裁剪到 30–365。
        include_etf_points: 是否带上每只 ETF 的完整点位序列。前端表格只用最新一天的
            标量，传 ``False`` 约省 65% 体积；缓存始终存完整响应。
        include_index_points: 是否带上指数点位序列。传 ``False`` 时标量仍保留，
            图表改由 ``get_national_team_index_series`` 单独获取。
        include_flow_breakdown: 是否带上 ``daily_flows[].flows_by_index``。前端只用
            ``flows_by_category``，可安全关闭。
    """
    response = await _resolve_response(days)
    if not include_flow_breakdown:
        response = without_flow_breakdown(response)
    if not include_index_points:
        response = without_index_points(response)
    return response if include_etf_points else without_etf_points(response)


async def get_national_team_index_series(days: int = 120) -> list[NationalTeamIndexSeries]:
    """返回完整指数点位序列，复用同一份缓存。"""
    return (await _resolve_response(days)).indices


async def get_national_team_index_series_item(
    index_key: str,
    days: int = 120,
) -> NationalTeamIndexSeries | None:
    """返回单条指数点位序列，供图表逐图懒加载。"""
    return next(
        (item for item in (await _resolve_response(days)).indices if item.index_key == index_key),
        None,
    )


async def get_national_team_overview(days: int = 120) -> NationalTeamOverview:
    """返回只含结论与标量的首屏概览，复用完整响应缓存。"""
    return build_national_team_overview(await _resolve_response(days))


def build_national_team_overview(
    response: NationalTeamResponse,
    *,
    history_days: int = 30,
) -> NationalTeamOverview:
    """从完整响应裁剪出首页信号卡需要的字段。"""
    history = response.support_score_history[-history_days:] if history_days > 0 else []
    return NationalTeamOverview(
        source=response.source,
        fetched_at=response.fetched_at,
        as_of_date=response.as_of_date,
        expected_date=response.expected_date,
        partial=response.partial,
        stale=response.stale,
        calendar_degraded=response.calendar_degraded,
        refreshing=response.refreshing,
        covered_etf_count=response.covered_etf_count,
        total_etf_count=response.total_etf_count,
        # 拷贝一份，避免调用方拿到缓存对象后意外修改。
        summary=response.summary.model_copy(deep=True),
        support_score=response.support_score.model_copy(deep=True),
        support_score_history=[point.model_copy(deep=True) for point in history],
        disclaimer=response.disclaimer,
    )


async def _resolve_response(days: int) -> NationalTeamResponse:
    days = max(30, min(days, 365))
    cached = market_cache.get(_response_cache_key(days))
    if cached is not None:
        cached_resp = NationalTeamResponse.model_validate(cached)
        has_indices = any(
            any(p.index_close is not None for p in idx.points)
            for idx in cached_resp.indices
        )
        if has_indices:
            return cached_resp

    stale = _stale_responses.get(str(days))
    if stale is not None:
        has_indices = any(
            any(p.index_close is not None for p in idx.points)
            for idx in stale.indices
        )
        if has_indices:
            _start_refresh(days)
            # 不改 fetched_at，不把缓存时间伪装成数据更新时间。
            response = NationalTeamResponse.model_validate(stale)
            now = datetime.now(SHANGHAI_TIMEZONE)
            fetched = datetime.fromisoformat(response.fetched_at).astimezone(SHANGHAI_TIMEZONE)
            # 跨日或跨过当日发布宽限后，旧日历不能证明当前新鲜度。
            calendar_expired = _calendar_window(fetched) != _calendar_window(now)
            return response.model_copy(
                update={
                    "partial": True,
                    "refreshing": str(days) in _refresh_tasks,
                    "calendar_degraded": response.calendar_degraded or calendar_expired,
                    "expected_date": None if calendar_expired else response.expected_date,
                }
            )

    return await _shared_response(days)


async def prewarm_national_team_prices() -> None:
    """预热监测页所需的指数与 ETF 日 K 缓存，避免页面首次访问时冷启动批量拉取触发超时。

    使用与 `_collect_response` 默认窗口相同的日期与数据源链路；不带单标的超时，
    让慢速上游排队完成后正常写入缓存。预热失败仅记录日志，不影响启动。
    """
    start, end = _response_window(120, datetime.now(SHANGHAI_TIMEZONE))
    start_text = start.strftime("%Y%m%d")
    end_text = end.strftime("%Y%m%d")

    async def load_index(key: str, definition: IndexDefinition) -> None:
        try:
            async with _price_semaphore:
                await _load_index_close_history(key, definition, start_text, end_text)
        except Exception as error:
            logger.info("国家队指数行情预热失败 index=%s error=%r", key, error)

    async def load_etf(code: str) -> None:
        try:
            async with _price_semaphore:
                await _load_etf_market_history(code, start_text, end_text)
        except Exception as error:
            logger.info("国家队 ETF 行情预热失败 code=%s error=%r", code, error)

    await asyncio.gather(
        *[load_index(key, definition) for key, definition in INDEX_POOL.items()],
        *[load_etf(code) for code in ETF_POOL],
    )


async def refresh_national_team_after_close(now: datetime | None = None) -> str:
    """收盘后把默认窗口的监测快照主动补齐一次。

    此前数据只在用户访问时才刷新：没人打开页面，收盘后的份额就永远缺席；而当天
    第一个访客要自己承担冷启动的 22 只 ETF + 10 个指数行情拉取。

    只在 16:00–18:00 窗口内动作，且每个业务日只完成一次：

    - 判断“完成”看的是 ``as_of_date == 当日 且 not partial``。交易所份额发布常
      晚于 16:00，若只看“跑过一次”就标记完成，当天永远不会再补；
    - 18:00 后不再尝试，避免非交易日/节假日全天反复请求上游；
    - 失败不做额外退避，由外层 5 分钟轮询节奏自然限流，底层源级冷却已拦得很密。

    Return:
        一个稳定的状态标签，便于测试与日志：``skipped_before_close`` /
        ``skipped_after_window`` / ``skipped_not_trading_day`` /
        ``skipped_completed`` / ``refreshed`` / ``retry_partial`` / ``failed``。
    """
    moment = now or datetime.now(SHANGHAI_TIMEZONE)
    business_date, _released = _calendar_window(moment)
    if moment.hour < _AFTER_CLOSE_START_HOUR:
        return "skipped_before_close"
    if moment.hour >= _AFTER_CLOSE_END_HOUR:
        return "skipped_after_window"

    day_text = business_date.isoformat()
    with _metrics_lock:
        if _refresh_metrics["scheduled_completed_date"] == day_text:
            return "skipped_completed"
        _refresh_metrics["scheduled_business_date"] = day_text

    expected_dates, calendar_degraded = await _load_expected_trading_dates(
        business_date - timedelta(days=7),
        moment,
    )
    if calendar_degraded or day_text not in expected_dates:
        # 宁可不刷，也不要在非交易日把同一份数据反复拉一遍。
        return "skipped_not_trading_day"

    try:
        response = await _shared_response(_DEFAULT_REFRESH_DAYS, trigger="scheduled", force=True)
    except Exception as error:
        logger.warning("国家队收盘后刷新失败 error=%r", error)
        return "failed"

    if response.partial or response.as_of_date != day_text:
        logger.info(
            "国家队收盘后刷新未完成，等待份额发布 as_of=%s expected=%s partial=%s",
            response.as_of_date,
            day_text,
            response.partial,
        )
        return "retry_partial"

    with _metrics_lock:
        _refresh_metrics["scheduled_completed_date"] = day_text
    logger.info(
        "国家队收盘后刷新完成 as_of=%s covered=%s/%s",
        response.as_of_date,
        response.covered_etf_count,
        response.total_etf_count,
    )
    return "refreshed"
