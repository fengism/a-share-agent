"""市场日行情双阶段刷新、失败分区重试与查询服务。"""

from __future__ import annotations

import asyncio
import logging
import time as monotonic_time
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from functools import cache
from uuid import uuid4
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from app.core.exceptions import InvalidRequestError
from app.financial_data.market.trading_session import get_trading_calendar_view
from app.modules.market_daily.collectors import SnapshotDateExpiredError, collect_segment
from app.modules.market_daily.models import (
    CollectedMarketDailyBars,
    MarketDailyBarDeleteResult,
    MarketDailyBarPage,
    MarketDailyBarRefreshHistory,
    MarketDailyBarRefreshRequest,
    MarketDailyBarRefreshResult,
    MarketDailyBarRefreshStatus,
    MarketDailySegment,
    RefreshCheckpoint,
)
from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH
from app.modules.market_daily.repository import (
    InvalidMarketDailyCursorError,
    MarketDailyAttemptLease,
    MarketDailyBarRepository,
    StaleMarketDailyAttemptError,
)

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")
INITIAL_CONFIRMATION_TIME = time(16, 20)
RECHECK_CONFIRMATION_TIME = time(17, 0)
FAILED_RECOVERY_LOOKBACK_DAYS = 3
SEGMENTS: tuple[MarketDailySegment, ...] = ("cn_stock", "cn_index", "hk_stock", "hk_index")

_segment_locks: dict[tuple[date, RefreshCheckpoint, str], asyncio.Lock] = {}
_segment_locks_guard = asyncio.Lock()

Collector = Callable[[str, date], Awaitable[CollectedMarketDailyBars]]
MarketNowProvider = Callable[[], datetime]

@cache
def _exchange_calendar(name: str, year: int):
    """按市场和年份加载交易所日历，避免默认实例的日期范围限制。"""
    return xcals.get_calendar(
        name,
        start=f"{year}-01-01",
        end=f"{year}-12-31",
    )


def _is_exchange_trading_day(name: str, target: date) -> bool:
    try:
        return bool(_exchange_calendar(name, target.year).is_session(target.isoformat()))
    except Exception as error:
        # 交易日历包可能尚未发布未来年份（XSHG 当前仅到 2026）。不能让
        # 调度循环异常退出或把范围外日期全部误判为休市；仅在此异常场景
        # 保守回退到工作日，并由采集器的行情日期验证继续兜底。
        logger.warning(
            "交易所日历不可用，按工作日降级: exchange=%s date=%s error=%s",
            name, target, error,
        )
        return target.weekday() < 5


def _market_now() -> datetime:
    return datetime.now(MARKET_TIMEZONE)


def checkpoint_for(now: datetime) -> RefreshCheckpoint | None:
    local = now.astimezone(MARKET_TIMEZONE) if now.tzinfo else now.replace(tzinfo=MARKET_TIMEZONE)
    if local.time() >= RECHECK_CONFIRMATION_TIME:
        return "recheck"
    if local.time() >= INITIAL_CONFIRMATION_TIME:
        return "initial"
    return None


def _retry_delay(attempts: int, base_seconds: int) -> timedelta:
    return timedelta(seconds=min(30 * 60, base_seconds * (2 ** max(0, attempts - 1))))


def is_cn_trading_day(target: date) -> bool:
    """使用交易所 XSHG 日历识别 A 股周末及法定休市日。"""
    return _is_exchange_trading_day("XSHG", target)


def is_hk_trading_day(target: date) -> bool:
    """使用交易所 XHKG 日历识别港股周末及法定休市日。"""
    return _is_exchange_trading_day("XHKG", target)


async def _segment_lock(key: tuple[date, RefreshCheckpoint, str]) -> asyncio.Lock:
    async with _segment_locks_guard:
        return _segment_locks.setdefault(key, asyncio.Lock())


class MarketDailyBarService:
    def __init__(
        self,
        repository: MarketDailyBarRepository | None = None,
        *,
        collector: Collector = collect_segment,
        retry_base_seconds: int = 60,
        now_provider: MarketNowProvider = _market_now,
    ) -> None:
        self.repository = repository or MarketDailyBarRepository(MARKET_DAILY_DATABASE_PATH)
        self.collector = collector
        self.retry_base_seconds = retry_base_seconds
        self._now_provider = now_provider
        self._last_scheduled_poll = 0.0
        self._segment_completed_at: dict[tuple[date, RefreshCheckpoint, str], float] = {}
        self._worker_id = f"market-daily-{uuid4().hex}"

    async def initialize(self) -> None:
        await asyncio.to_thread(self.repository.initialize)

    async def _is_cn_trading_day(self, target: date) -> bool:
        calendar = await get_trading_calendar_view(target, target)
        if not calendar.degraded:
            return target.isoformat() in calendar.trade_dates
        # 远端 A 股日历不可用时不能按普通工作日判断，否则国庆等工作日假期
        # 会进入采集和重试；使用内置 XSHG 交易所日历作为确定性降级。
        return is_cn_trading_day(target)

    async def _is_hk_trading_day(self, target: date) -> bool:
        return is_hk_trading_day(target)

    async def run_scheduled(self, now: datetime | None = None) -> list[MarketDailyBarRefreshStatus]:
        """按动态配置的轮询间隔执行到期检查。"""
        from app.configuration import get_settings

        settings = get_settings()
        if not settings.market_daily_bar_refresh_enabled:
            return []
        self.retry_base_seconds = settings.market_daily_bar_refresh_retry_base_seconds
        current = monotonic_time.monotonic()
        if current - self._last_scheduled_poll < settings.market_daily_bar_refresh_poll_seconds:
            return []
        self._last_scheduled_poll = current
        return await self.run_due(now)

    async def run_due(self, now: datetime | None = None) -> list[MarketDailyBarRefreshStatus]:
        await self.initialize()
        local_now = now or self._now_provider()
        if local_now.tzinfo is None:
            local_now = local_now.replace(tzinfo=MARKET_TIMEZONE)
        else:
            local_now = local_now.astimezone(MARKET_TIMEZONE)
        await self._retry_recent_failed(local_now)
        checkpoint = checkpoint_for(local_now)
        if checkpoint is None:
            return []
        target = local_now.date()
        # 17:00 之后先补齐 16:20 阶段，再执行复核；失败分区按 next_retry_at 退避。
        checkpoints: tuple[RefreshCheckpoint, ...] = (
            ("initial", "recheck") if checkpoint == "recheck" else ("initial",)
        )
        cn_trading = await self._is_cn_trading_day(target)
        hk_trading = await self._is_hk_trading_day(target)
        for current_checkpoint in checkpoints:
            for segment in SEGMENTS:
                await self._run_segment(
                    target,
                    current_checkpoint,
                    segment,
                    local_now,
                    cn_trading=cn_trading,
                    hk_trading=hk_trading,
                )
        return await asyncio.to_thread(self.repository.list_status, target)

    async def _retry_recent_failed(self, now: datetime) -> None:
        """安全补偿近期跨日失败任务；采集器仍必须确认上游数据属于目标日期。"""
        end_date = now.date() - timedelta(days=1)
        start_date = end_date - timedelta(days=FAILED_RECOVERY_LOOKBACK_DAYS - 1)
        failed, _ = await asyncio.to_thread(
            self.repository.list_refresh_history,
            start_date=start_date,
            end_date=end_date,
            status="failed",
            limit=len(SEGMENTS) * 2 * FAILED_RECOVERY_LOOKBACK_DAYS,
            offset=0,
        )
        cn_trading_by_date: dict[date, bool] = {}
        hk_trading_by_date: dict[date, bool] = {}
        for item in reversed(failed):
            if item.segment not in SEGMENTS:
                continue
            cn_trading = False
            hk_trading = False
            if item.segment.startswith("cn_"):
                if item.trade_date not in cn_trading_by_date:
                    cn_trading_by_date[item.trade_date] = await self._is_cn_trading_day(item.trade_date)
                cn_trading = cn_trading_by_date[item.trade_date]
            elif item.segment.startswith("hk_"):
                if item.trade_date not in hk_trading_by_date:
                    hk_trading_by_date[item.trade_date] = await self._is_hk_trading_day(item.trade_date)
                hk_trading = hk_trading_by_date[item.trade_date]
            await self._run_segment(
                item.trade_date,
                item.checkpoint,
                item.segment,
                now,
                cn_trading=cn_trading,
                hk_trading=hk_trading,
            )

    async def _run_segment(
        self,
        target: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        now: datetime,
        *,
        cn_trading: bool,
        hk_trading: bool,
        force: bool = False,
        requested_at: float | None = None,
    ) -> bool:
        key = (target, checkpoint, segment)
        request_version = requested_at if requested_at is not None else monotonic_time.monotonic()
        lock = await _segment_lock(key)
        async with lock:
            if force and self._segment_completed_at.get(key, -1.0) >= request_version:
                return False
            lease = await asyncio.to_thread(
                self.repository.claim_attempt,
                target,
                checkpoint,
                segment,
                started_at=now,
                worker_id=self._worker_id,
                force=force,
            )
            if lease is None:
                return False
            await self._run_segment_locked(
                target, checkpoint, segment, now, lease=lease,
                cn_trading=cn_trading, hk_trading=hk_trading,
            )
            self._segment_completed_at[key] = monotonic_time.monotonic()
            return True

    async def _run_segment_locked(
        self,
        target: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        now: datetime,
        *,
        lease: MarketDailyAttemptLease,
        cn_trading: bool,
        hk_trading: bool,
    ) -> None:
        # A/H 交易日历并非完全一致，分别按 SSE/SZSE 与 XHKG 日历判断。
        # 采集器的行情日期校验仍作为上游数据完整性的第二道保护。
        if segment.startswith("cn_") and not cn_trading:
            note = "A 股非交易日（交易日历）"
            await asyncio.to_thread(
                self.repository.record_skipped, target, checkpoint, segment, note,
                attempt_id=lease.attempt_id,
            )
            logger.info(
                "市场日行情分区跳过: date=%s checkpoint=%s segment=%s reason=%s",
                target, checkpoint, segment, note,
            )
            return
        if segment.startswith("hk_") and not hk_trading:
            note = "港股非交易日（XHKG 日历）"
            await asyncio.to_thread(
                self.repository.record_skipped, target, checkpoint, segment, note,
                attempt_id=lease.attempt_id,
            )
            logger.info(
                "市场日行情分区跳过: date=%s checkpoint=%s segment=%s reason=%s",
                target, checkpoint, segment, note,
            )
            return
        try:
            result = await self.collector(segment, target)
            if result.no_session:
                await asyncio.to_thread(
                    self.repository.record_skipped,
                    target,
                    checkpoint,
                    segment,
                    result.note or "非交易日",
                    attempt_id=lease.attempt_id,
                )
                return
            stored = await asyncio.to_thread(
                self.repository.persist_refresh,
                target,
                checkpoint,
                segment,
                result.records,
                refreshed_at=now,
                attempt_id=lease.attempt_id,
                source=result.source,
            )
            logger.info(
                "市场日行情刷新完成: date=%s checkpoint=%s segment=%s source=%s rows=%s",
                target,
                checkpoint,
                segment,
                result.source,
                stored,
            )
        except SnapshotDateExpiredError as error:
            await asyncio.to_thread(
                self.repository.record_skipped,
                target,
                checkpoint,
                segment,
                f"{error}；请清理后通过历史行情导入重建",
                attempt_id=lease.attempt_id,
            )
            logger.warning(
                "市场日行情快照已过期，停止无效重试: date=%s checkpoint=%s segment=%s",
                target,
                checkpoint,
                segment,
            )
        except StaleMarketDailyAttemptError:
            logger.info(
                "市场日行情任务租约已被接管，忽略旧 worker 结果: "
                "date=%s checkpoint=%s segment=%s",
                target, checkpoint, segment,
            )
        except Exception as error:
            retry_at = now + _retry_delay(lease.attempts, self.retry_base_seconds)
            await asyncio.to_thread(
                self.repository.record_failure,
                target,
                checkpoint,
                segment,
                error,
                retry_at,
                attempt_id=lease.attempt_id,
            )
            logger.warning(
                "市场日行情分区刷新失败，将重试: date=%s checkpoint=%s segment=%s attempts=%s retry_at=%s",
                target,
                checkpoint,
                segment,
                lease.attempts,
                retry_at.isoformat(),
                exc_info=True,
            )

    async def refresh(
        self,
        request: MarketDailyBarRefreshRequest,
    ) -> MarketDailyBarRefreshResult:
        from app.configuration import get_settings

        request_started_at = monotonic_time.monotonic()
        self.retry_base_seconds = get_settings().market_daily_bar_refresh_retry_base_seconds
        local_now = self._now_provider().astimezone(MARKET_TIMEZONE)
        if request.trade_date != local_now.date():
            raise InvalidRequestError(
                "全市场手动刷新仅支持今天；历史日期可查看或清理，但不能用当前快照重建"
            )
        required_time = (
            INITIAL_CONFIRMATION_TIME
            if request.checkpoint == "initial"
            else RECHECK_CONFIRMATION_TIME
        )
        if local_now.time() < required_time:
            raise InvalidRequestError(
                f"{request.checkpoint} 阶段需等待到 {required_time.strftime('%H:%M')} 后再刷新"
            )
        await self.initialize()
        segments = list(dict.fromkeys(request.segments or SEGMENTS))
        if request.retry_failed_only:
            failed = {
                item.segment
                for item in await asyncio.to_thread(self.repository.list_status, request.trade_date)
                if item.checkpoint == request.checkpoint and item.status == "failed"
            }
            segments = [segment for segment in segments if segment in failed]
        cn_trading = (
            await self._is_cn_trading_day(request.trade_date)
            if any(segment.startswith("cn_") for segment in segments)
            else False
        )
        hk_trading = (
            await self._is_hk_trading_day(request.trade_date)
            if any(segment.startswith("hk_") for segment in segments)
            else False
        )
        now = datetime.now(MARKET_TIMEZONE)
        for segment in segments:
            await self._run_segment(
                request.trade_date,
                request.checkpoint,
                segment,
                now,
                cn_trading=cn_trading,
                hk_trading=hk_trading,
                force=request.force or request.retry_failed_only,
                requested_at=request_started_at,
            )
        return MarketDailyBarRefreshResult(
            trade_date=request.trade_date,
            checkpoint=request.checkpoint,
            requested_segments=segments,
            statuses=await asyncio.to_thread(self.repository.list_status, request.trade_date),
        )

    async def refresh_history(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> MarketDailyBarRefreshHistory:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidRequestError("start_date 不能晚于 end_date")
        await self.initialize()
        items, total = await asyncio.to_thread(
            self.repository.list_refresh_history,
            start_date=start_date,
            end_date=end_date,
            status=status,
            limit=limit,
            offset=offset,
        )
        return MarketDailyBarRefreshHistory(items=items, total=total, limit=limit, offset=offset)

    async def delete_day(
        self,
        *,
        trade_date: date,
        segments: list[MarketDailySegment] | None = None,
        rebuild: bool = False,
        checkpoint: RefreshCheckpoint = "recheck",
    ) -> MarketDailyBarDeleteResult:
        local_today = self._now_provider().astimezone(MARKET_TIMEZONE).date()
        if rebuild and trade_date != local_today:
            raise InvalidRequestError(
                "历史日期不能用当前全市场快照重建；请仅清理或使用历史 K 线数据源"
            )
        await self.initialize()
        selected = list(dict.fromkeys(segments or SEGMENTS))
        phases: tuple[RefreshCheckpoint, ...] = ("initial", "recheck")
        lock_keys = [(trade_date, phase, segment) for phase in phases for segment in selected]
        locks = [await _segment_lock(key) for key in lock_keys]
        for lock in locks:
            await lock.acquire()
        try:
            bars, observations, jobs = await asyncio.to_thread(
                self.repository.delete_day, trade_date, segments=selected
            )
        finally:
            for lock in reversed(locks):
                lock.release()
        rebuild_result = None
        if rebuild:
            rebuild_result = await self.refresh(
                MarketDailyBarRefreshRequest(
                    trade_date=trade_date,
                    checkpoint=checkpoint,
                    segments=selected,
                    force=True,
                )
            )
        return MarketDailyBarDeleteResult(
            trade_date=trade_date,
            deleted_bars=bars,
            deleted_observations=observations,
            deleted_jobs=jobs,
            rebuild_result=rebuild_result,
        )

    async def query(
        self,
        *,
        market: str | None = None,
        instrument_type: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        codes: list[str] | None = None,
        page: int = 1,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> MarketDailyBarPage:
        if cursor and page != 1:
            raise InvalidRequestError("cursor 分页不能与 page>1 同时使用")
        if trade_date is not None and (start_date is not None or end_date is not None):
            raise InvalidRequestError("trade_date 不能与 start_date/end_date 同时使用")
        if (start_date is None) != (end_date is None):
            raise InvalidRequestError("start_date 和 end_date 必须同时提供")
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidRequestError("start_date 不能晚于 end_date")
        await self.initialize()
        try:
            return await asyncio.to_thread(
                self.repository.query,
                market=market,
                instrument_type=instrument_type,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                codes=codes,
                page=page,
                page_size=page_size,
                cursor=cursor,
            )
        except InvalidMarketDailyCursorError as error:
            raise InvalidRequestError(str(error)) from error

    async def maintain_storage(
        self,
        *,
        observation_retention_days: int,
        attempt_retention_days: int,
        now: datetime | None = None,
    ) -> dict[str, object]:
        await self.initialize()
        local_now = (now or self._now_provider()).astimezone(MARKET_TIMEZONE)
        deleted = await asyncio.to_thread(
            self.repository.prune_audit_history,
            observations_before=local_now.date() - timedelta(days=observation_retention_days),
            attempts_before=local_now.date() - timedelta(days=attempt_retention_days),
        )
        storage = await asyncio.to_thread(self.repository.optimize_storage)
        return {
            "deleted_observations": deleted[0],
            "deleted_runs": deleted[1],
            "deleted_attempts": deleted[2],
            **storage,
        }

    async def status(self, trade_date: date) -> list[MarketDailyBarRefreshStatus]:
        await self.initialize()
        return await asyncio.to_thread(self.repository.list_status, trade_date)


market_daily_bar_service = MarketDailyBarService()
