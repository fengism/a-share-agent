"""申万2级行业市场宽度计算（收盘价站上 MA20 的股票占比）。"""

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime

from app.configuration.paths import DATA_DIR
from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.domain.market import KlineData
from app.financial_data.market.quotes.schemas import (
    MarketBreadthDailySummary,
    MarketBreadthResponse,
)
from app.financial_data.market.trading_session import (
    SHANGHAI_TIMEZONE,
    get_completed_market_date,
    get_trading_calendar_view,
    resolve_market_data_cache_policy,
)
from app.financial_data.stock.quotes.historical import HistoricalRequestLimiter
from app.financial_data.stock.quotes.kline import get_kline
from app.financial_data.stock.quotes.technical import calculate_ma
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.modules.industry_classification.repository import a_share_all_levels_mapping

logger = logging.getLogger(__name__)

MA_PERIOD = 20
_DEFAULT_DAYS = 60
_MAX_DAYS = 120
_MIN_DAYS = 10
_WORKER_CONCURRENCY = 4
_MAX_PROVIDER_SOURCES = 2
_STRONG_BREADTH_THRESHOLD = 50.0
_SNAPSHOT_VERSION = 1
_BREADTH_SOURCE_INTERVALS = {
    "tdxhub": 0.2,
    "tencent": 0.25,
    "akshare": 0.5,
    "eastmoney": 1.0,
    "cls": 0.5,
}


@dataclass
class _SourceRateState:
    next_allowed_at: float = 0.0
    cooldown_until: float = 0.0


class BreadthRequestLimiter(HistoricalRequestLimiter):
    """市场宽度批量任务使用的 Provider 级启动间隔与共享冷却。"""

    def __init__(
        self,
        source_intervals: dict[str, float],
        *,
        jitter_seconds: float = 0.1,
        cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._source_intervals = source_intervals
        self._jitter_seconds = max(0.0, jitter_seconds)
        self._cooldown_seconds = max(0.0, cooldown_seconds)
        self._clock = clock
        self._sleep = sleep
        self._states: dict[str, _SourceRateState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _interval_for(self, source: str) -> float:
        for prefix, interval in self._source_intervals.items():
            if source.startswith(prefix):
                return max(0.0, interval)
        return 0.5

    def _state_for(self, source: str) -> _SourceRateState:
        return self._states.setdefault(source, _SourceRateState())

    def _lock_for(self, source: str) -> asyncio.Lock:
        return self._locks.setdefault(source, asyncio.Lock())

    async def wait(self, source: str) -> None:
        """串行化同一 Provider 的请求启动，并在 429 后等待共享冷却。"""
        async with self._lock_for(source):
            state = self._state_for(source)
            now = self._clock()
            ready_at = max(state.next_allowed_at, state.cooldown_until)
            jitter = random.uniform(0.0, self._jitter_seconds)
            delay = max(0.0, ready_at - now) + jitter
            if delay > 0:
                await self._sleep(delay)
            effective_now = max(self._clock(), now + delay)
            state.next_allowed_at = effective_now + self._interval_for(source)

    async def observe_error(self, source: str, error: Exception) -> None:
        """识别异常链中的限流响应，并将冷却时间共享给后续请求。"""
        retry_after = _rate_limit_retry_after(error)
        if retry_after is None:
            return
        cooldown = max(self._cooldown_seconds, retry_after)
        async with self._lock_for(source):
            state = self._state_for(source)
            state.cooldown_until = max(state.cooldown_until, self._clock() + cooldown)
        logger.warning("市场宽度数据源 %s 触发限流，共享冷却 %.1f 秒", source, cooldown)


_breadth_request_limiter = BreadthRequestLimiter(_BREADTH_SOURCE_INTERVALS)
_breadth_singleflight: AsyncSingleFlight[MarketBreadthResponse] = AsyncSingleFlight()


def _exception_chain(error: Exception):
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _retry_after_seconds(value: object) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        pass
    try:
        retry_at = parsedate_to_datetime(str(value))
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def _rate_limit_retry_after(error: Exception) -> float | None:
    """返回限流冷却秒数；非限流异常返回 None。"""
    rate_limited = False
    retry_after: float | None = None
    for candidate in _exception_chain(error):
        response = getattr(candidate, "response", None)
        status_code = getattr(candidate, "status_code", None) or getattr(response, "status_code", None)
        headers = getattr(response, "headers", None) or getattr(candidate, "headers", None) or {}
        message = str(candidate).lower()
        if status_code == 429 or any(
            marker in message
            for marker in ("429", "too many requests", "rate limit", "访问频繁", "限流")
        ):
            rate_limited = True
            parsed_retry_after = _retry_after_seconds(headers.get("Retry-After"))
            if parsed_retry_after is not None:
                retry_after = max(retry_after or 0.0, parsed_retry_after)
    if not rate_limited:
        return None
    return retry_after or 0.0


def _snapshot_path(days: int):
    return DATA_DIR / f"market_breadth_sw2_{days}.json"


def _load_breadth_snapshot(days: int) -> tuple[str, MarketBreadthResponse] | None:
    path = _snapshot_path(days)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != _SNAPSHOT_VERSION or payload.get("days") != days:
            return None
        response = MarketBreadthResponse.model_validate(payload["response"])
        completed_market_date = str(
            payload.get("completed_market_date") or response.completed_market_date
        )
        if not completed_market_date:
            return None
        return completed_market_date, response
    except FileNotFoundError:
        return None
    except (OSError, TypeError, ValueError, KeyError) as error:
        logger.warning("读取市场宽度快照失败: path=%s error=%s", path, error)
        return None


def _save_breadth_snapshot(
    days: int,
    completed_market_date: date,
    response: MarketBreadthResponse,
) -> None:
    persisted = response.model_copy(
        update={"completed_market_date": completed_market_date.isoformat(), "stale": False}
    )
    atomic_write_json(
        _snapshot_path(days),
        {
            "version": _SNAPSHOT_VERSION,
            "days": days,
            "completed_market_date": completed_market_date.isoformat(),
            "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "response": persisted.model_dump(mode="json"),
        },
    )


def _stale_snapshot(snapshot: tuple[str, MarketBreadthResponse]) -> MarketBreadthResponse:
    return snapshot[1].model_copy(update={"stale": True})


def _trade_date_window(trade_dates: list[str], days: int) -> list[str]:
    """截取最近 days+MA 个交易日作为统计窗口，保证 MA20 有足够样本。"""
    needed = days + MA_PERIOD + 5
    if len(trade_dates) <= needed:
        return trade_dates
    return trade_dates[-needed:]


def _aggregate_industry(
    window_dates: list[str],
    stocks: list[tuple[str, str]],
    klines: dict[str, KlineData | None],
) -> tuple[list[str], list[list[float | None]]]:
    """按申万2级行业聚合每日站上 MA20 的股票占比。"""
    date_index = {day: idx for idx, day in enumerate(window_dates)}
    industry_stocks: dict[str, list[str]] = {}
    for code, industry in stocks:
        industry_stocks.setdefault(industry, []).append(code)

    industries = sorted(industry_stocks)
    values: list[list[float | None]] = []

    for industry in industries:
        strong_counts = [0] * len(window_dates)
        valid_counts = [0] * len(window_dates)
        for code in industry_stocks[industry]:
            kline = klines.get(code)
            if kline is None or not kline.items:
                continue
            closes: list[float] = []
            item_keys: list[str] = []
            item_map: dict[str, list[float]] = {}
            for item in kline.items:
                if item.date not in date_index:
                    continue
                item_map.setdefault(item.date, []).append(item.close)
            sorted_keys = sorted(item_map)
            for key in sorted_keys:
                closes.append(item_map[key][0])
                item_keys.append(key)
            mas = calculate_ma(closes, MA_PERIOD)
            for pos, key in enumerate(item_keys):
                window_idx = date_index[key]
                ma = mas[pos]
                close = closes[pos]
                if ma is None:
                    continue
                valid_counts[window_idx] += 1
                if close > ma:
                    strong_counts[window_idx] += 1
        industry_values: list[float | None] = []
        for idx in range(len(window_dates)):
            if valid_counts[idx] == 0:
                industry_values.append(None)
            else:
                industry_values.append(round(strong_counts[idx] / valid_counts[idx] * 100, 1))
        values.append(industry_values)

    return industries, values


def _build_summaries(
    window_dates: list[str],
    output_dates: list[str],
    values: list[list[float | None]],
    industries: list[str],
) -> list[MarketBreadthDailySummary]:
    """构建每日强势行业数量与占比摘要。"""
    summaries: list[MarketBreadthDailySummary] = []
    date_index = {day: idx for idx, day in enumerate(window_dates)}
    for day in output_dates:
        idx = date_index[day]
        strong_count = 0
        total_count = 0
        for industry_idx, _industry in enumerate(industries):
            ratio = values[industry_idx][idx]
            if ratio is None:
                continue
            total_count += 1
            if ratio >= _STRONG_BREADTH_THRESHOLD:
                strong_count += 1
        ratio = round(strong_count / total_count * 100, 1) if total_count else 0.0
        summaries.append(
            MarketBreadthDailySummary(
                date=day,
                strong_industry_count=strong_count,
                total_industry_count=total_count,
                strong_ratio=ratio,
            )
        )
    return summaries


async def _load_stock_kline(
    code: str,
    start_date: str,
    end_date: str,
    request_limiter: HistoricalRequestLimiter,
) -> KlineData | None:
    try:
        return await get_kline(
            code,
            start_date=start_date,
            end_date=end_date,
            max_provider_sources=_MAX_PROVIDER_SOURCES,
            request_limiter=request_limiter,
        )
    except Exception as error:  # noqa: BLE001 - 单只股票失败不阻断整体
        logger.warning("市场宽度股票 %s K线加载失败: %s", code, error)
        return None


async def _load_stock_klines(
    stocks: list[tuple[str, str]],
    start_date: str,
    end_date: str,
    *,
    request_limiter: HistoricalRequestLimiter = _breadth_request_limiter,
) -> dict[str, KlineData]:
    """使用固定数量 worker 和有界队列加载全市场 K 线。"""
    if not stocks:
        return {}
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=_WORKER_CONCURRENCY * 2)
    klines: dict[str, KlineData] = {}

    async def worker() -> None:
        while True:
            code = await queue.get()
            try:
                if code is None:
                    return
                kline = await _load_stock_kline(code, start_date, end_date, request_limiter)
                if kline is not None:
                    klines[code] = kline
            finally:
                queue.task_done()

    worker_count = min(_WORKER_CONCURRENCY, len(stocks))
    workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
    try:
        for code, _industry in stocks:
            await queue.put(code)
        for _ in workers:
            await queue.put(None)
        await queue.join()
        await asyncio.gather(*workers)
    finally:
        for task in workers:
            if not task.done():
                task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    return klines


async def get_market_breadth(days: int = _DEFAULT_DAYS) -> MarketBreadthResponse:
    """获取申万2级行业市场宽度，支持持久化快照与失败降级。"""
    days = max(_MIN_DAYS, min(days, _MAX_DAYS))
    snapshot = _load_breadth_snapshot(days)
    try:
        today = datetime.now(SHANGHAI_TIMEZONE).date()
        end_date = await get_completed_market_date(today)
        policy = await resolve_market_data_cache_policy("daily", end_date)
    except Exception:  # noqa: BLE001 - 基础日期服务失败时优先保证已有快照可用
        if snapshot is not None:
            logger.exception("市场宽度日期准备失败，返回最近成功快照")
            return _stale_snapshot(snapshot)
        raise

    cache_key = dated_cache_key("market_breadth_sw2", days)
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketBreadthResponse.model_validate(cached)

    if snapshot is not None and snapshot[0] == end_date.isoformat():
        return snapshot[1].model_copy(update={"stale": False})

    async def _load() -> MarketBreadthResponse:
        calendar_start = end_date - timedelta(days=int((days + MA_PERIOD + 10) / 5 * 7) + 7)
        calendar_view = await get_trading_calendar_view(calendar_start, end_date)
        trade_dates = calendar_view.trade_dates
        if not trade_dates:
            raise ValueError("交易日历为空")
        window_dates = _trade_date_window(trade_dates, days)
        fetch_start = window_dates[0]
        output_dates = trade_dates if len(trade_dates) < days else trade_dates[-days:]

        mapping = a_share_all_levels_mapping()
        stocks: list[tuple[str, str]] = []
        seen_codes: set[str] = set()
        for code, info in mapping.items():
            bare_code = code.split(".", 1)[0] if "." in code else code
            if bare_code in seen_codes:
                continue
            seen_codes.add(bare_code)
            level2 = info.get("level2") or ""
            if level2:
                stocks.append((bare_code, level2))

        klines = await _load_stock_klines(stocks, fetch_start, end_date.isoformat())
        if not klines:
            raise UpstreamUnavailableError("市场宽度未加载到任何有效股票 K 线")
        logger.info("市场宽度 K 线加载完成: success=%d total=%d", len(klines), len(stocks))

        industries, values = _aggregate_industry(window_dates, stocks, klines)
        summaries = _build_summaries(window_dates, output_dates, values, industries)
        output_start = max(0, len(window_dates) - len(output_dates))
        final_dates = window_dates[output_start:] if window_dates else output_dates
        output_values = [row[output_start:] if output_start < len(row) else [] for row in values]

        return MarketBreadthResponse(
            industries=industries,
            dates=final_dates,
            values=output_values,
            summaries=summaries,
            fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
            completed_market_date=end_date.isoformat(),
            successful_stocks=len(klines),
            total_stocks=len(stocks),
        )

    try:
        result = await _breadth_singleflight.do(cache_key, _load)
    except Exception:  # noqa: BLE001 - 整体刷新失败时返回最近成功快照
        if snapshot is not None:
            logger.exception("市场宽度刷新失败，返回最近成功快照")
            return _stale_snapshot(snapshot)
        raise

    try:
        _save_breadth_snapshot(days, end_date, result)
    except OSError as error:
        logger.warning("写入市场宽度快照失败: %s", error)
    if policy.write_cache and policy.ttl_seconds is not None:
        cache.set(cache_key, result, ttl=policy.ttl_seconds)
    return result
