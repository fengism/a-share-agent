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
