"""A 股交易时段感知的行情缓存策略。"""

import logging
import math
from collections.abc import Set
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from app.core.cache import TTLCache
from app.core.concurrency.rate_limiter import akshare_semaphore, call_blocking
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
TRADING_WINDOW_START = time(9, 0)
TRADING_WINDOW_END = time(15, 30)
STABLE_MARKET_DATA_CACHE_TTL_SECONDS = 24 * 60 * 60
_TRADING_CALENDAR_CACHE_KEY = "a_share_trading_dates"
_TRADING_CALENDAR_SUCCESS_TTL_SECONDS = 24 * 60 * 60
_TRADING_CALENDAR_FAILURE_TTL_SECONDS = 5 * 60
_MAX_NEXT_OPEN_SEARCH_DAYS = 370


@dataclass(frozen=True)
class MarketDataCachePolicy:
    """描述一次行情请求是否读写缓存以及缓存时长。"""

    read_cache: bool
    write_cache: bool
    ttl_seconds: int | None


@dataclass(frozen=True)
class _TradingCalendarSnapshot:
    trading_dates: frozenset[date] | None


_trading_calendar_cache = TTLCache(maxsize=1, name="trading_calendar")
_trading_calendar_singleflight = AsyncSingleFlight[_TradingCalendarSnapshot]()


def _get_akshare_provider():
    return get_provider("akshare")


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=SHANGHAI_TIMEZONE)
    return now.astimezone(SHANGHAI_TIMEZONE)


def _is_trading_date(day: date, trading_dates: Set[date] | None) -> bool:
    if trading_dates is None:
        return day.weekday() < 5
    return day in trading_dates


def _next_trading_open(now: datetime, trading_dates: Set[date] | None) -> datetime:
    for day_offset in range(_MAX_NEXT_OPEN_SEARCH_DAYS + 1):
        candidate_date = now.date() + timedelta(days=day_offset)
        if not _is_trading_date(candidate_date, trading_dates):
            continue
        candidate = datetime.combine(candidate_date, TRADING_WINDOW_START, tzinfo=SHANGHAI_TIMEZONE)
        if candidate > now:
            return candidate

    fallback_date = now.date() + timedelta(days=1)
    while fallback_date.weekday() >= 5:
        fallback_date += timedelta(days=1)
    return datetime.combine(fallback_date, TRADING_WINDOW_START, tzinfo=SHANGHAI_TIMEZONE)


def build_market_data_cache_policy(
    *,
    period: str,
    end_date: date,
    now: datetime,
    trading_dates: Set[date] | None,
) -> MarketDataCachePolicy:
    """根据行情周期、日期范围和当前交易状态构造缓存策略。"""
    local_now = _normalize_now(now)
    if period != "daily" or end_date < local_now.date():
        return MarketDataCachePolicy(
            read_cache=True,
            write_cache=True,
            ttl_seconds=STABLE_MARKET_DATA_CACHE_TTL_SECONDS,
        )

    effective_trading_dates = trading_dates
    if trading_dates is not None and (not trading_dates or max(trading_dates) < local_now.date()):
        effective_trading_dates = None

    is_live = (
        _is_trading_date(local_now.date(), effective_trading_dates)
        and TRADING_WINDOW_START <= local_now.time().replace(tzinfo=None) <= TRADING_WINDOW_END
    )
    if is_live:
        return MarketDataCachePolicy(read_cache=False, write_cache=False, ttl_seconds=None)

    next_open = _next_trading_open(local_now, effective_trading_dates)
    ttl_seconds = max(1, math.ceil((next_open - local_now).total_seconds()))
    return MarketDataCachePolicy(read_cache=True, write_cache=True, ttl_seconds=ttl_seconds)


async def _load_trading_calendar() -> _TradingCalendarSnapshot:
    try:
        values = await call_blocking(
            _get_akshare_provider().fetch_trade_dates,
            semaphore=akshare_semaphore,
        )
        trading_dates = frozenset(values)
        if not trading_dates:
            raise ValueError("交易日历为空")
        snapshot = _TradingCalendarSnapshot(trading_dates=trading_dates)
        ttl_seconds = _TRADING_CALENDAR_SUCCESS_TTL_SECONDS
    except Exception as error:
        logger.warning("A 股交易日历加载失败，按工作日实时策略降级: %s", error)
        snapshot = _TradingCalendarSnapshot(trading_dates=None)
        ttl_seconds = _TRADING_CALENDAR_FAILURE_TTL_SECONDS

    _trading_calendar_cache.set(_TRADING_CALENDAR_CACHE_KEY, snapshot, ttl=ttl_seconds)
    return snapshot


async def _get_trading_calendar() -> _TradingCalendarSnapshot:
    cached = _trading_calendar_cache.get(_TRADING_CALENDAR_CACHE_KEY)
    if cached is not None:
        return cast(_TradingCalendarSnapshot, cached)
    return cast(
        _TradingCalendarSnapshot,
        await _trading_calendar_singleflight.do(_TRADING_CALENDAR_CACHE_KEY, _load_trading_calendar),
    )


async def resolve_market_data_cache_policy(
    period: str,
    end_date: date,
    *,
    now: datetime | None = None,
) -> MarketDataCachePolicy:
    """解析一次行情请求使用的交易时段缓存策略。"""
    local_now = _normalize_now(now)
    if period != "daily" or end_date < local_now.date():
        return build_market_data_cache_policy(
            period=period,
            end_date=end_date,
            now=local_now,
            trading_dates=None,
        )

    calendar = await _get_trading_calendar()
    return build_market_data_cache_policy(
        period=period,
        end_date=end_date,
        now=local_now,
        trading_dates=calendar.trading_dates,
    )


def completed_market_date(
    requested_end_date: date,
    *,
    now: datetime,
    trading_dates: Set[date] | None,
) -> date:
    """Resolve a requested daily end date to the latest completed A-share session."""
    local_now = _normalize_now(now)
    if requested_end_date < local_now.date():
        return requested_end_date

    effective_trading_dates = trading_dates
    if trading_dates is not None and (not trading_dates or max(trading_dates) < local_now.date()):
        effective_trading_dates = None

    candidate = min(requested_end_date, local_now.date())
    today_is_completed = (
        _is_trading_date(local_now.date(), effective_trading_dates)
        and local_now.time().replace(tzinfo=None) > TRADING_WINDOW_END
    )
    if candidate == local_now.date() and not today_is_completed:
        candidate -= timedelta(days=1)
    while not _is_trading_date(candidate, effective_trading_dates):
        candidate -= timedelta(days=1)
    return candidate


async def get_completed_market_date(
    requested_end_date: date,
    *,
    now: datetime | None = None,
) -> date:
    local_now = _normalize_now(now)
    if requested_end_date < local_now.date():
        return requested_end_date
    calendar = await _get_trading_calendar()
    return completed_market_date(
        requested_end_date,
        now=local_now,
        trading_dates=calendar.trading_dates,
    )


def market_date_on_or_before(
    requested_date: date,
    *,
    trading_dates: Set[date] | None,
) -> date:
    """Resolve any historical date to the nearest A-share session on or before it."""
    effective_trading_dates = trading_dates
    if trading_dates is not None and (not trading_dates or max(trading_dates) < requested_date):
        effective_trading_dates = None
    candidate = requested_date
    while not _is_trading_date(candidate, effective_trading_dates):
        candidate -= timedelta(days=1)
    return candidate


async def get_market_date_on_or_before(requested_date: date) -> date:
    calendar = await _get_trading_calendar()
    return market_date_on_or_before(requested_date, trading_dates=calendar.trading_dates)

async def get_trading_calendar_view(
    start_date: date | None = None,
    end_date: date | None = None,
) -> "TradingCalendarResponse":  # noqa: F821
    """公开的交易日历查询：区间列表 + 今日状态 + 前后交易日。"""
    from app.financial_data.market.quotes.schemas import TradingCalendarResponse

    snapshot = await _get_trading_calendar()
    trading_dates = snapshot.trading_dates
    today = _normalize_now(None).date()

    if trading_dates is None:
        # 日历源不可用时按工作日近似并标记降级
        fallback: list[date] = []
        cursor = start_date or today
        bound = end_date or (today + timedelta(days=365))
        while cursor <= bound and len(fallback) <= 8000:
            if cursor.weekday() < 5:
                fallback.append(cursor)
            cursor += timedelta(days=1)
        dates = fallback
        degraded = True
    else:
        dates = sorted(
            day
            for day in trading_dates
            if (start_date is None or day >= start_date)
            and (end_date is None or day <= end_date)
        )
        degraded = False

    def _previous(day: date) -> str | None:
        if trading_dates is None:
            probe = day - timedelta(days=1)
            while probe.weekday() >= 5:
                probe -= timedelta(days=1)
            return probe.isoformat()
        return max((d for d in trading_dates if d < day), default=None).isoformat() if any(d < day for d in trading_dates) else None

    def _next(day: date) -> str | None:
        if trading_dates is None:
            probe = day + timedelta(days=1)
            while probe.weekday() >= 5:
                probe += timedelta(days=1)
            return probe.isoformat()
        return min((d for d in trading_dates if d > day), default=None).isoformat() if any(d > day for d in trading_dates) else None

    return TradingCalendarResponse(
        start_date=(start_date or (dates[0] if dates else today)).isoformat(),
        end_date=(end_date or (dates[-1] if dates else today)).isoformat(),
        trade_dates=[day.isoformat() for day in dates],
        count=len(dates),
        today=today.isoformat(),
        today_is_trading_day=_is_trading_date(today, trading_dates),
        previous_trading_day=_previous(today),
        next_trading_day=_next(today),
        degraded=degraded,
    )
