"""核心宽基 ETF 份额变化与国家队持仓代理监测。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
from app.financial_data.market.quotes.schemas import (
    NationalTeamEtfPoint,
    NationalTeamEtfSeries,
    NationalTeamIndexPoint,
    NationalTeamIndexSeries,
    NationalTeamResponse,
    NationalTeamShareObservation,
    NationalTeamSummary,
)
from app.financial_data.market.trading_session import get_trading_calendar_view
from app.financial_data.stock.quotes.kline import get_kline
from app.infrastructure.persistence import national_team_etf_store
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_LEGACY_SNAPSHOT_PATH = Path(__file__).resolve().parents[4] / "data" / "national_team_etf" / "shares.json"

logger = logging.getLogger(__name__)

_METHOD = "按 ETF 逐只计算：份额变化 × 当日 ETF 收盘价，并在宽基层级汇总；份额单位为亿份，资金单位为亿元。"
_DISCLAIMER = (
    "ETF 份额变化仅是观察国家队资金行为的代理指标，不等于中央汇金真实持仓；申购赎回可能来自其他机构或个人投资者。"
)


_YI = 100_000_000
_SZSE_MAX_WINDOW_DAYS = 7
_SZSE_MAX_WINDOWS_PER_REFRESH = 8
_SZSE_REQUEST_INTERVAL_SECONDS = 0.15
_REFRESH_TIMEOUT_SECONDS = 15.0
# 优先腾讯财经极速日K；若需回退TDX排队或重试，120s/45s 充足预算避免无谓超时截断
_PRICE_TIMEOUT_SECONDS = 120.0
_PRICE_ITEM_TIMEOUT_SECONDS = 45.0
_SOURCE_TIMEOUT_SECONDS = 10.0
_price_semaphore = asyncio.Semaphore(8)
_source_limits = {
    "sse": asyncio.Semaphore(4),
    "szse_history": asyncio.Semaphore(1),
    "szse_current": asyncio.Semaphore(1),
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
                    _source_cooldowns.set(scope, True, ttl=60)
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
        "sse": asyncio.Semaphore(4),
        "szse_history": asyncio.Semaphore(1),
        "szse_current": asyncio.Semaphore(1),
    }
    _price_semaphore = asyncio.Semaphore(4)
    _active_tasks.clear()
    _refresh_cooldowns.clear()
    _source_cooldowns.clear()
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


@dataclass(frozen=True, slots=True)
class EtfDefinition:
    code: str
    name: str
    fund_manager: str
    exchange: Literal["SH", "SZ"]
    index_key: str


@dataclass(frozen=True, slots=True)
class IndexDefinition:
    key: str
    name: str
    index_code: str


INDEX_POOL: dict[str, IndexDefinition] = {
    "csi300": IndexDefinition("csi300", "沪深300", "000300.SH"),
    "sz50": IndexDefinition("sz50", "上证50", "000016.SH"),
    "csi500": IndexDefinition("csi500", "中证500", "000905.SH"),
    "csi1000": IndexDefinition("csi1000", "中证1000", "000852.SH"),
    "star50": IndexDefinition("star50", "科创50", "000688.SH"),
    "chinext": IndexDefinition("chinext", "创业板", "399006.SZ"),
}

ETF_POOL: dict[str, EtfDefinition] = {
    "510300": EtfDefinition("510300", "华泰柏瑞沪深300ETF", "华泰柏瑞基金", "SH", "csi300"),
    "510310": EtfDefinition("510310", "易方达沪深300ETF", "易方达基金", "SH", "csi300"),
    "510330": EtfDefinition("510330", "华夏沪深300ETF", "华夏基金", "SH", "csi300"),
    "159919": EtfDefinition("159919", "嘉实沪深300ETF", "嘉实基金", "SZ", "csi300"),
    "510050": EtfDefinition("510050", "华夏上证50ETF", "华夏基金", "SH", "sz50"),
    "510500": EtfDefinition("510500", "南方中证500ETF", "南方基金", "SH", "csi500"),
    "512100": EtfDefinition("512100", "南方中证1000ETF", "南方基金", "SH", "csi1000"),
    "159845": EtfDefinition("159845", "华夏中证1000ETF", "华夏基金", "SZ", "csi1000"),
    "560010": EtfDefinition("560010", "广发中证1000ETF", "广发基金", "SH", "csi1000"),
    "159629": EtfDefinition("159629", "富国中证1000ETF", "富国基金", "SZ", "csi1000"),
    "588080": EtfDefinition("588080", "易方达上证科创板50ETF", "易方达基金", "SH", "star50"),
    "159915": EtfDefinition("159915", "易方达创业板ETF", "易方达基金", "SZ", "chinext"),
}


def _rounded(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _period_change(values: dict[str, float], dates: list[str], sessions: int) -> float | None:
    if len(dates) <= sessions:
        return None
    latest = values.get(dates[-1])
    baseline = values.get(dates[-1 - sessions])
    return None if latest is None or baseline is None else _rounded(latest - baseline)


def _sum_complete(values: list[float | None]) -> float | None:
    if not values or any(value is None for value in values):
        return None
    return _rounded(sum(value for value in values if value is not None))


def _period_flow(points: list[NationalTeamEtfPoint], dates: list[str], sessions: int) -> float | None:
    if len(dates) <= sessions:
        return None
    flows = {point.date: point.estimated_net_flow_100m for point in points}
    # 窗口首日仅作基线；之后每个交易日都必须具备可比份额和收盘价。
    return _sum_complete([flows.get(day) for day in dates[max(1, len(dates) - sessions) :]])


def _build_etf_series(
    definition: EtfDefinition,
    shares: dict[str, float],
    closes: dict[str, float],
    dates: list[str],
) -> NationalTeamEtfSeries:
    points: list[NationalTeamEtfPoint] = []
    previous_dates = dict(zip(dates[1:], dates))
    for point_date in sorted(shares):
        previous_shares = shares.get(previous_dates.get(point_date, ""))
        absolute_shares = float(shares[point_date])
        shares_100m = absolute_shares / _YI
        change_100m = None if previous_shares is None else (absolute_shares - previous_shares) / _YI
        close = closes.get(point_date)
        change_pct = (
            None if previous_shares in (None, 0) else (absolute_shares - previous_shares) / previous_shares * 100
        )
        flow = None if change_100m is None or close is None else change_100m * close
        points.append(
            NationalTeamEtfPoint(
                date=point_date,
                shares_100m=round(shares_100m, 4),
                shares_change_100m=_rounded(change_100m),
                shares_change_pct=_rounded(change_pct),
                close=_rounded(close),
                estimated_net_flow_100m=_rounded(flow),
            )
        )
    share_values = {point.date: point.shares_100m for point in points}
    latest = points[-1] if points else None
    is_current = latest is not None and bool(dates) and latest.date == dates[-1]
    index = INDEX_POOL[definition.index_key]
    return NationalTeamEtfSeries(
        code=definition.code,
        name=definition.name,
        fund_manager=definition.fund_manager,
        exchange=definition.exchange,
        index_key=definition.index_key,
        index_name=index.name,
        latest_date=latest.date if latest else None,
        latest_shares_100m=latest.shares_100m if latest else None,
        latest_change_1d_100m=latest.shares_change_100m if is_current else None,
        change_5d_100m=_period_change(share_values, dates, 5),
        change_20d_100m=_period_change(share_values, dates, 20),
        points=points,
    )


def _build_index_series(
    definition: IndexDefinition,
    etfs: list[NationalTeamEtfSeries],
    closes: dict[str, float],
    dates: list[str],
) -> NationalTeamIndexSeries:
    member_codes = [item.code for item in ETF_POOL.values() if item.index_key == definition.key]
    point_maps = {
        item.code: {point.date: point for point in item.points}
        for item in etfs
        if item.index_key == definition.key and item.points
    }
    # 成员集合固定；某只 ETF 某日缺失时不生成缩小覆盖范围的聚合点。
    complete_dates = sorted(set.intersection(*(set(mapping) for mapping in point_maps.values()))) if point_maps else []
    points: list[NationalTeamIndexPoint] = []
    first_total: float | None = None
    for point_date in complete_dates:
        day_points = [mapping[point_date] for mapping in point_maps.values()]
        total = sum(point.shares_100m for point in day_points)
        if first_total is None:
            first_total = total
        change = _sum_complete([point.shares_change_100m for point in day_points])
        flows = [point.estimated_net_flow_100m for point in day_points]
        points.append(
            NationalTeamIndexPoint(
                date=point_date,
                total_shares_100m=round(total, 4),
                shares_change_100m=_rounded(change),
                cumulative_change_100m=_rounded(total - first_total) or 0,
                index_close=_rounded(closes.get(point_date)),
                estimated_net_flow_100m=_sum_complete(flows),
            )
        )
    totals = {point.date: point.total_shares_100m for point in points}
    latest = points[-1] if points else None
    is_current = latest is not None and bool(dates) and latest.date == dates[-1]
    return NationalTeamIndexSeries(
        index_key=definition.key,
        index_name=definition.name,
        index_code=definition.index_code,
        etf_codes=member_codes,
        covered_etf_codes=list(point_maps),
        latest_date=latest.date if latest else None,
        latest_total_shares_100m=latest.total_shares_100m if latest else None,
        latest_change_1d_100m=latest.shares_change_100m if is_current else None,
        change_5d_100m=_period_change(totals, dates, 5),
        change_20d_100m=_period_change(totals, dates, 20),
        estimated_net_flow_1d_100m=latest.estimated_net_flow_100m if is_current else None,
        points=points,
    )


def build_national_team_response(
    *,
    share_history: dict[str, dict[str, float]],
    etf_close_history: dict[str, dict[str, float]],
    index_close_history: dict[str, dict[str, float]],
    fetched_at: str,
    requested_days: int,
    expected_trading_dates: list[str] | None = None,
    calendar_degraded: bool = False,
    share_metadata: dict[str, dict[str, dict]] | None = None,
    observations: list[NationalTeamShareObservation] | None = None,
) -> NationalTeamResponse:
    """将份额与行情映射转换为 API 响应；该函数保持纯计算以便测试。"""
    share_dates = {day for code in ETF_POOL for day in share_history.get(code, {})}
    price_dates = {
        day for history in (etf_close_history, index_close_history) for values in history.values() for day in values
    }
    calendar_degraded = calendar_degraded or expected_trading_dates is None
    expected_dates = share_dates | price_dates | set(expected_trading_dates or [])
    expected_date = max(expected_trading_dates or [], default=None)
    as_of_date = max(share_dates, default=None)
    dates = sorted(day for day in expected_dates if as_of_date and day <= as_of_date)
    etfs = [
        _build_etf_series(definition, share_history.get(code, {}), etf_close_history.get(code, {}), dates)
        for code, definition in ETF_POOL.items()
    ]
    indices = [
        _build_index_series(definition, etfs, index_close_history.get(key, {}), dates)
        for key, definition in INDEX_POOL.items()
    ]
    for item in etfs:
        for point in item.points:
            metadata = (share_metadata or {}).get(item.code, {}).get(point.date, {})
            point.source = metadata.get("source", "unknown")
            point.fetched_at = metadata.get("fetched_at")
            point.verification_status = metadata.get("verification_status", "unknown")
    if not expected_trading_dates and not price_dates:
        # 纯存量冷启动时不知道缺了哪些交易日，不把样本点数当交易日数。
        for item in [*etfs, *indices]:
            item.latest_change_1d_100m = None
            item.change_5d_100m = None
            item.change_20d_100m = None
            for point in item.points:
                point.shares_change_100m = None
                point.estimated_net_flow_100m = None
        for item in etfs:
            for point in item.points:
                point.shares_change_pct = None
        for item in indices:
            item.estimated_net_flow_1d_100m = None
    populated = [item for item in etfs if item.points and item.latest_date == as_of_date]
    missing_share_etfs = [
        code
        for code in ETF_POOL
        if not share_history.get(code) or not expected_dates.issubset(share_history.get(code, {}))
    ]
    missing_price_etfs = [
        code
        for code in ETF_POOL
        if not etf_close_history.get(code) or not expected_dates.issubset(etf_close_history.get(code, {}))
    ]
    missing_indices = [
        key
        for key in INDEX_POOL
        if not index_close_history.get(key) or not expected_dates.issubset(index_close_history.get(key, {}))
    ]
    missing_etfs = sorted(set(missing_share_etfs) | set(missing_price_etfs))
    stale = bool(expected_date and (as_of_date is None or as_of_date < expected_date))
    summary = NationalTeamSummary(
        total_shares_100m=_sum_complete([item.latest_shares_100m for item in populated]),
        change_1d_100m=_sum_complete([item.latest_change_1d_100m for item in populated]),
        change_5d_100m=_sum_complete([item.change_5d_100m for item in populated]),
        change_20d_100m=_sum_complete([item.change_20d_100m for item in populated]),
        estimated_net_flow_1d_100m=_sum_complete(
            [item.points[-1].estimated_net_flow_100m if item.points else None for item in populated]
        ),
        estimated_net_flow_5d_100m=_sum_complete([_period_flow(item.points, dates, 5) for item in populated]),
        estimated_net_flow_20d_100m=_sum_complete([_period_flow(item.points, dates, 20) for item in populated]),
    )
    return NationalTeamResponse(
        fetched_at=fetched_at,
        as_of_date=as_of_date,
        requested_days=requested_days,
        observations=observations or [],
        partial=bool(missing_etfs or missing_indices or stale or calendar_degraded),
        expected_date=expected_date,
        stale=stale,
        calendar_degraded=calendar_degraded,
        missing_share_etfs=missing_share_etfs,
        missing_price_etfs=missing_price_etfs,
        missing_indices=missing_indices,
        covered_etf_count=len(populated),
        total_etf_count=len(ETF_POOL),
        missing_etfs=missing_etfs,
        methodology=_METHOD,
        disclaimer=_DISCLAIMER,
        summary=summary,
        indices=indices,
        etfs=etfs,
    )


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
        max_attempts=1,
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
    semaphore = asyncio.Semaphore(4)
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

    tasks = [asyncio.create_task(fetch(day)) for day in reversed(missing_dates)]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # 共享请求已完成但结果尚未交付等待方时，取消也不能丢失进度。
        for day in missing_dates:
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
                    shares_100m=shares / _YI,
                    fetched_at=fetched_at,
                )

    try:
        async with asyncio.timeout(3.0):
            merge(await _fetch_szse_current_direct(), "szse_current")
    except Exception as error:
        logger.warning("深交所 ETF 当前份额直连失败 error=%r", error)

    missing_codes = target_codes.difference(result)
    if missing_codes:
        try:
            async with asyncio.timeout(2.0):
                merge(await _fetch_szse_current_eastmoney(missing_codes), "eastmoney_current")
        except Exception as error:
            logger.warning("深交所 ETF 当前份额东财备选数据源失败 error=%r", error)
    if not result:
        raise UpstreamUnavailableError("深交所 ETF 当前份额所有数据源均不可用")
    return result


def _write_observations(values: dict[str, NationalTeamShareObservation]) -> None:
    national_team_etf_store.save_observations(
        (point.code, point.source, point.shares_100m * _YI, datetime.fromisoformat(point.fetched_at).timestamp())
        for point in values.values()
    )


def _read_provenance() -> tuple[dict[str, dict[str, dict]], list[NationalTeamShareObservation]]:
    observations = [
        NationalTeamShareObservation(
            code=row["code"],
            source=row["source"],
            shares_100m=row["shares"] / _YI,
            fetched_at=datetime.fromtimestamp(row["fetched_at"], UTC).isoformat(timespec="seconds"),
        )
        for row in national_team_etf_store.load_observations(ETF_POOL)
        if row["fetched_at"] >= datetime.now(UTC).timestamp() - 86400
    ]
    return national_team_etf_store.load_share_metadata(ETF_POOL), observations


async def _load_etf_close_history(
    code: str,
    start_date: str,
    end_date: str,
) -> dict[str, float]:
    """优先从腾讯财经拉取 ETF 收盘价（轻量快速且无单线程互斥锁），失败时平滑回退 get_kline。"""
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
        logger.debug("腾讯财经获取 ETF %s 行情失败，回退 get_kline: %r", code, error)

    data = await get_kline(
        code,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="",
        max_provider_sources=2,
    )
    return {item.date: item.close for item in data.items}


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
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    etf_history: dict[str, dict[str, float]] = {}
    index_history: dict[str, dict[str, float]] = {}

    async def load_etf(code: str) -> tuple[str, dict[str, float]]:
        try:
            async with _price_semaphore:
                async with asyncio.timeout(_PRICE_ITEM_TIMEOUT_SECONDS):
                    closes = await _load_etf_close_history(code, start_date, end_date)
                    etf_history[code] = closes
                    return code, closes
        except Exception as error:
            logger.warning("国家队 ETF 行情获取失败 code=%s error=%r", code, error)
            return code, {}

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

    # 优先加载 6 只核心指数行情，确保大盘基准与走势图完整呈现；随后加载 12 只 ETF 行情
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
    return etf_history, index_history


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
        if exchange != "SZ" or latest != now.date().isoformat() or now.hour < 16:
            return
        missing = {code for code in codes if latest not in share_history.get(code, {})}
        if not missing:
            return
        try:
            async with asyncio.timeout(6.0):
                values = await _source_request("szse_current", latest, _fetch_szse_current)
            # 没有业务日期的当前快照只能作为独立观察，不进入历史或回填完成标记。
            await call_blocking(_write_observations, values, semaphore=misc_semaphore)
        except Exception as error:
            logger.warning("国家队当前份额刷新失败 error=%r", error)

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


async def _collect_response(days: int = 120) -> NationalTeamResponse:
    """返回核心宽基 ETF 份额与指数价格的国家队代理监测视图。"""
    days = max(30, min(days, 365))
    now = datetime.now(SHANGHAI_TIMEZONE)
    cache_key = _response_cache_key(days, now)
    cached = market_cache.get(cache_key)
    if cached is not None:
        return NationalTeamResponse.model_validate(cached)

    start, end = _response_window(days, now)
    (expected_trading_dates, calendar_degraded), (etf_closes, index_closes) = await asyncio.gather(
        _load_expected_trading_dates(start, now),
        _load_price_history(start.strftime("%Y%m%d"), end.strftime("%Y%m%d")),
    )

    start_iso, end_iso = start.isoformat(), end.isoformat()
    etf_closes, index_closes = (
        {
            key: {day: value for day, value in values.items() if start_iso <= day <= end_iso}
            for key, values in history.items()
        }
        for history in (etf_closes, index_closes)
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


async def _shared_response(days: int) -> NationalTeamResponse:
    if _stopping:
        raise asyncio.CancelledError

    async def load() -> NationalTeamResponse:
        task = asyncio.current_task()
        _active_tasks.add(task)
        try:
            return await _collect_response(days)
        finally:
            _active_tasks.discard(task)

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


async def get_national_team_etf_holdings(days: int = 120) -> NationalTeamResponse:
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
                await _load_etf_close_history(code, start_text, end_text)
        except Exception as error:
            logger.info("国家队 ETF 行情预热失败 code=%s error=%r", code, error)

    await asyncio.gather(
        *[load_index(key, definition) for key, definition in INDEX_POOL.items()],
        *[load_etf(code) for code in ETF_POOL],
    )
