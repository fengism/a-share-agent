"""管理员触发的 A 股全市场历史日线回填任务。"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.core.exceptions import ResourceConflictError, ResourceNotFoundError
from app.financial_data.market.quotes.breadth import BreadthRequestLimiter
from app.financial_data.stock.public import get_exchange_stock_master
from app.financial_data.stock.quotes.historical import (
    HistoricalBarCandidates,
    HistoricalBarSet,
    get_historical_bar_candidates,
)
from app.modules.market_daily.models import (
    MarketDailyBackfillJob,
    MarketDailyBackfillJobList,
    MarketDailyBackfillRequest,
    MarketDailyBarRecord,
)
from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH
from app.modules.market_daily.repository import MarketDailyBarRepository

logger = logging.getLogger(__name__)

_BACKFILL_SOURCE_INTERVALS = {
    "tdxhub": 0.15,
    "tencent": 0.25,
    "akshare": 0.5,
    "eastmoney": 1.0,
    "cls": 0.5,
    "sina": 0.5,
}
_FAILURE_DETAIL_LIMIT = 100
_LEASE_SECONDS = 15 * 60
_WORKER_CONCURRENCY = 4
_MIN_DATE_COVERAGE = 0.95
_MAX_OHLC_RELATIVE_ERROR = 0.005
_MAX_VOLUME_MEDIAN_ERROR = 0.02
_MAX_AMOUNT_MEDIAN_ERROR = 0.02
_MAX_VOLUME_PRICE_RATIO_ERROR = 0.15

_FAILURE_UPSTREAM = "upstream_unavailable"
_FAILURE_INCONSISTENT = "source_inconsistent"
_FAILURE_INVALID = "invalid_data"
_RETRYABLE_FAILURE_KINDS = {_FAILURE_UPSTREAM}


class HistoricalSourceConsistencyError(ValueError):
    """两个独立历史行情源无法满足一致性阈值。"""


class HistoricalSourceAvailabilityError(RuntimeError):
    """临时上游错误导致无法获得足够的独立数据源。"""


@dataclass(frozen=True)
class BackfillValidation:
    primary: HistoricalBarSet
    secondary: HistoricalBarSet
    score: float
    details: dict[str, object]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds")


def _job_from_row(row) -> MarketDailyBackfillJob:
    payload = dict(row)
    try:
        payload["failure_details"] = json.loads(payload.pop("failure_details_json") or "[]")
    except (TypeError, ValueError):
        payload["failure_details"] = []
    for key in ("overwrite_existing", "cancel_requested"):
        payload[key] = bool(payload[key])
    payload.pop("lease_owner", None)
    payload.pop("lease_expires_at", None)
    return MarketDailyBackfillJob.model_validate(payload)




def _source_family(source: str) -> str:
    if source.startswith("tdxhub"):
        return "tdxhub"
    if source.startswith("tencent"):
        return "tencent"
    if source.startswith("akshare-sina") or source.startswith("sina-direct"):
        return "sina"
    if source.startswith("eastmoney") or source.startswith("akshare-eastmoney"):
        return "eastmoney"
    if source.startswith("cls"):
        return "cls"
    return source


def _relative_error(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), 1e-12)
    return abs(left - right) / scale


def _median_relative_error(pairs: list[tuple[float, float]]) -> float | None:
    errors = [_relative_error(left, right) for left, right in pairs if left >= 0 and right >= 0]
    return statistics.median(errors) if errors else None


def _validate_candidate_pair(
    primary: HistoricalBarSet,
    secondary: HistoricalBarSet,
) -> BackfillValidation:
    primary_by_date = {item.date: item for item in primary.items}
    secondary_by_date = {item.date: item for item in secondary.items}
    primary_dates = set(primary_by_date)
    secondary_dates = set(secondary_by_date)
    common_dates = sorted(primary_dates & secondary_dates)
    expected_dates = max(len(primary_dates), len(secondary_dates))
    date_coverage = len(common_dates) / expected_dates if expected_dates else 0.0
    if date_coverage < _MIN_DATE_COVERAGE:
        raise HistoricalSourceConsistencyError(
            f"source_inconsistent: 日期覆盖不足 primary={primary.source} secondary={secondary.source} "
            f"common={len(common_dates)} expected={expected_dates} coverage={date_coverage:.1%}"
        )

    ohlc_errors: list[float] = []
    volume_pairs: list[tuple[float, float]] = []
    amount_pairs: list[tuple[float, float]] = []
    for trade_date in common_dates:
        left = primary_by_date[trade_date]
        right = secondary_by_date[trade_date]
        for field in ("open", "high", "low", "close"):
            l_val = getattr(left, field)
            r_val = getattr(right, field)
            if l_val is not None and r_val is not None:
                ohlc_errors.append(_relative_error(l_val, r_val))
        if left.volume is not None and right.volume is not None and left.volume >= 0 and right.volume >= 0:
            volume_pairs.append((left.volume, right.volume))
        if left.amount is not None and right.amount is not None and left.amount >= 0 and right.amount >= 0:
            amount_pairs.append((left.amount, right.amount))

    max_ohlc_error = max(ohlc_errors, default=0.0)
    volume_error = _median_relative_error(volume_pairs)
    amount_error = _median_relative_error(amount_pairs)
    if max_ohlc_error > _MAX_OHLC_RELATIVE_ERROR:
        raise HistoricalSourceConsistencyError(
            f"source_inconsistent: OHLC 偏差过大 primary={primary.source} secondary={secondary.source} "
            f"max_error={max_ohlc_error:.2%}"
        )
    if volume_error is None or volume_error > _MAX_VOLUME_MEDIAN_ERROR:
        raise HistoricalSourceConsistencyError(
            f"source_inconsistent: 成交量偏差过大 primary={primary.source} secondary={secondary.source} "
            f"median_error={volume_error if volume_error is not None else 'missing'}"
        )
    if amount_error is not None and amount_error > _MAX_AMOUNT_MEDIAN_ERROR:
        raise HistoricalSourceConsistencyError(
            f"source_inconsistent: 成交额偏差过大 primary={primary.source} secondary={secondary.source} "
            f"median_error={amount_error:.2%}"
        )

    score = 100.0
    score -= (1.0 - date_coverage) * 40.0
    score -= min(25.0, max_ohlc_error / _MAX_OHLC_RELATIVE_ERROR * 25.0)
    score -= min(20.0, (volume_error or 0.0) / _MAX_VOLUME_MEDIAN_ERROR * 20.0)
    score -= min(15.0, (amount_error or 0.0) / _MAX_AMOUNT_MEDIAN_ERROR * 15.0)
    details = {
        "primary_source": primary.source,
        "secondary_source": secondary.source,
        "primary_rows": len(primary.items),
        "secondary_rows": len(secondary.items),
        "common_dates": len(common_dates),
        "date_coverage": round(date_coverage, 6),
        "max_ohlc_relative_error": round(max_ohlc_error, 8),
        "median_volume_relative_error": round(volume_error or 0.0, 8),
        "median_amount_relative_error": round(amount_error, 8) if amount_error is not None else None,
    }
    return BackfillValidation(
        primary=primary,
        secondary=secondary,
        score=round(max(0.0, score), 2),
        details=details,
    )


def _validate_candidate_quality(history: HistoricalBarSet) -> dict[str, object]:
    ratios = [
        item.amount / (item.volume * item.close)
        for item in history.items
        if item.amount > 0 and item.volume > 0 and item.close > 0
    ]
    ratio_median = statistics.median(ratios) if ratios else None
    if ratio_median is not None and abs(ratio_median - 1.0) > _MAX_VOLUME_PRICE_RATIO_ERROR:
        raise HistoricalSourceConsistencyError(
            f"source_inconsistent: 成交额/成交量/价格口径异常 source={history.source} "
            f"median={ratio_median:.4f}"
        )
    def _is_valid_numeric(val: float | None) -> bool:
        return val is None or (isinstance(val, (int, float)) and math.isfinite(val))

    if any(
        not (item.close is not None and item.close > 0 and math.isfinite(item.close))
        or not all(_is_valid_numeric(v) for v in (item.open, item.high, item.low, item.volume, item.amount))
        for item in history.items
    ):
        raise ValueError(f"历史行情包含非有限数值或非法收盘价: source={history.source}")
    return {
        "amount_volume_close_ratio_median": round(ratio_median, 6) if ratio_median is not None else None,
        "amount_available": ratio_median is not None,
    }


def _select_validated_candidate(candidates: HistoricalBarCandidates) -> BackfillValidation:
    if len(candidates.candidates) < 2:
        failures = "; ".join(
            f"{failure.source_label}:{failure.error_type}:{failure.error_message}"
            for failure in candidates.failures
        )
        detail = failures or "仅一个来源返回数据"
        lowered = detail.lower()
        if any(token in lowered for token in (
            "connection", "timeout", "timed out", "unavailable", "连接", "429", "限流", "circuit",
        )):
            raise HistoricalSourceAvailabilityError(
                f"上游暂时无法提供至少两个独立数据源；{detail}"
            )
        raise ValueError(f"至少需要两个独立有效数据源；{detail}")

    valid_pairs: list[tuple[int, int, BackfillValidation]] = []
    pair_errors: list[str] = []
    for left_index, primary in enumerate(candidates.candidates):
        for right_index in range(left_index + 1, len(candidates.candidates)):
            secondary = candidates.candidates[right_index]
            if _source_family(primary.source) == _source_family(secondary.source):
                pair_errors.append(
                    f"非独立来源: {primary.source} / {secondary.source}"
                )
                continue
            try:
                validation = _validate_candidate_pair(primary, secondary)
                quality = _validate_candidate_quality(primary)
            except HistoricalSourceConsistencyError as error:
                pair_errors.append(str(error))
                continue
            valid_pairs.append((left_index, right_index, BackfillValidation(
                primary=validation.primary,
                secondary=validation.secondary,
                score=validation.score,
                details={
                    **validation.details,
                    **quality,
                    "failed_sources": [
                        {
                            "source": failure.source_label,
                            "error_type": failure.error_type,
                            "error": failure.error_message,
                        }
                        for failure in candidates.failures
                    ],
                },
            )))
    if not valid_pairs:
        raise HistoricalSourceConsistencyError(
            "source_inconsistent: 无任意两个成功来源满足一致性阈值；" + "；".join(pair_errors[:3])
        )
    # 严格遵循来源优先级：先找能被任一独立次源验证的最高优先级主源；
    # 只有该主源与所有次源都冲突时才降级。相同主源下再取质量分最高的一对。
    best_primary_index = min(pair[0] for pair in valid_pairs)
    primary_pairs = [pair for pair in valid_pairs if pair[0] == best_primary_index]
    _, _, selected = max(primary_pairs, key=lambda pair: (pair[2].score, -pair[1]))
    return selected


def _records_from_history(code: str, name: str, history: HistoricalBarSet) -> list[MarketDailyBarRecord]:
    records: list[MarketDailyBarRecord] = []
    for item in history.items:
        trade_date = date.fromisoformat(item.date)
        pre_close = item.pre_close
        change_amount = item.close - pre_close if pre_close is not None else None
        records.append(
            MarketDailyBarRecord(
                market="cn",
                instrument_type="stock",
                code=code,
                name=name,
                trade_date=trade_date,
                currency="CNY",
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                pre_close=pre_close,
                change_amount=change_amount,
                change_pct=item.change_pct,
                volume=item.volume,
                amount=item.amount,
                turnover_pct=item.turnover_pct,
                source=f"history-backfill:{history.source}",
            )
        )
    return records


def _failure_kind(error: Exception) -> str:
    if isinstance(error, HistoricalSourceConsistencyError):
        return _FAILURE_INCONSISTENT
    if isinstance(error, HistoricalSourceAvailabilityError):
        return _FAILURE_UPSTREAM
    text = str(error).lower()
    if any(token in text for token in ("上游", "timeout", "timed out", "connection", "连接", "429", "限流", "unavailable")):
        return _FAILURE_UPSTREAM
    return _FAILURE_INVALID


class MarketDailyBackfillService:
    def __init__(self, repository: MarketDailyBarRepository | None = None) -> None:
        self.repository = repository or MarketDailyBarRepository(MARKET_DAILY_DATABASE_PATH)
        self._worker_id = uuid4().hex
        self._limiter = BreadthRequestLimiter(_BACKFILL_SOURCE_INTERVALS)

    async def initialize(self) -> None:
        await asyncio.to_thread(self.repository.initialize)

    async def create(self, request: MarketDailyBackfillRequest) -> MarketDailyBackfillJob:
        await self.initialize()
        active_job_id = await asyncio.to_thread(self._active_job_id)
        if active_job_id is not None:
            raise ResourceConflictError(f"已有历史回填任务正在执行: {active_job_id}")
        master = await get_exchange_stock_master()
        records = [
            record
            for record in master.records
            if record.exchange in {"SH", "SZ", "BJ"}
            and (not record.listing_date or record.listing_date <= request.end_date.isoformat())
        ]
        if not records:
            raise ResourceConflictError("A 股股票主表为空，无法创建历史回填任务")
        return await asyncio.to_thread(self._create_job, request, records)

    def _active_job_id(self) -> str | None:
        with self.repository._connect() as connection:
            row = connection.execute(
                "SELECT job_id FROM market_daily_backfill_jobs WHERE status IN ('pending','running') LIMIT 1"
            ).fetchone()
        return str(row["job_id"]) if row is not None else None

    def _create_job(self, request: MarketDailyBackfillRequest, records) -> MarketDailyBackfillJob:
        job_id = uuid4().hex
        now = _iso()
        with self.repository._connect() as connection:  # 同模块内部持久化，复用 WAL/事务配置
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                "SELECT job_id FROM market_daily_backfill_jobs WHERE status IN ('pending','running') LIMIT 1"
            ).fetchone()
            if active is not None:
                raise ResourceConflictError(f"已有历史回填任务正在执行: {active['job_id']}")
            connection.execute(
                """
                INSERT INTO market_daily_backfill_jobs (
                    job_id, market, instrument_type, start_date, end_date,
                    overwrite_existing, max_provider_sources, status,
                    total_instruments, created_at, updated_at
                ) VALUES (?, 'cn', 'stock', ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    job_id, request.start_date.isoformat(), request.end_date.isoformat(),
                    int(request.overwrite_existing), request.max_provider_sources,
                    len(records), now, now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO market_daily_backfill_items (
                    job_id, code, name, exchange, status, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                [(job_id, record.code, record.name, record.exchange, now) for record in records],
            )
            row = connection.execute(
                "SELECT * FROM market_daily_backfill_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return _job_from_row(row)

    async def list_jobs(self, *, limit: int = 20) -> MarketDailyBackfillJobList:
        await self.initialize()
        return await asyncio.to_thread(self._list_jobs, limit)

    def _list_jobs(self, limit: int) -> MarketDailyBackfillJobList:
        with self.repository._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM market_daily_backfill_jobs").fetchone()[0])
            rows = connection.execute(
                "SELECT * FROM market_daily_backfill_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return MarketDailyBackfillJobList(items=[_job_from_row(row) for row in rows], total=total)

    async def get(self, job_id: str) -> MarketDailyBackfillJob:
        await self.initialize()
        job = await asyncio.to_thread(self._get, job_id)
        if job is None:
            raise ResourceNotFoundError("历史回填任务不存在")
        return job

    def _get(self, job_id: str) -> MarketDailyBackfillJob | None:
        with self.repository._connect() as connection:
            row = connection.execute(
                "SELECT * FROM market_daily_backfill_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return _job_from_row(row) if row is not None else None

    async def retry_failed(self, job_id: str) -> MarketDailyBackfillJob:
        """仅重新排队指定任务中失败的股票，保留已成功结果。"""
        await self.initialize()
        await asyncio.to_thread(self._retry_failed, job_id)
        return await self.get(job_id)

    def _retry_failed(self, job_id: str) -> None:
        now = _iso()
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = connection.execute(
                "SELECT status FROM market_daily_backfill_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if job is None:
                raise ResourceNotFoundError("历史回填任务不存在")
            if job["status"] in {"pending", "running"}:
                raise ResourceConflictError("历史回填任务仍在执行，无需重试")
            active = connection.execute(
                """
                SELECT job_id FROM market_daily_backfill_jobs
                WHERE job_id<>? AND status IN ('pending','running') LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            if active is not None:
                raise ResourceConflictError(f"已有历史回填任务正在执行: {active['job_id']}")
            failed = int(connection.execute(
                "SELECT COUNT(*) FROM market_daily_backfill_items WHERE job_id=? AND status='failed' AND failure_kind='upstream_unavailable'",
                (job_id,),
            ).fetchone()[0])
            if failed == 0:
                raise ResourceConflictError("该任务没有失败股票需要重试")
            connection.execute(
                """
                UPDATE market_daily_backfill_items
                SET status='pending', stored_bars=0, source=NULL, quality_score=NULL,
                    validation_json=NULL, failure_kind=NULL, last_error=NULL, updated_at=?
                WHERE job_id=? AND status='failed' AND failure_kind='upstream_unavailable'
                """,
                (now, job_id),
            )
            connection.execute(
                """
                UPDATE market_daily_backfill_jobs SET
                    status='pending',
                    completed_instruments=(
                        SELECT COUNT(*) FROM market_daily_backfill_items
                        WHERE job_id=? AND status IN ('succeeded','failed','skipped')
                    ),
                    succeeded_instruments=(
                        SELECT COUNT(*) FROM market_daily_backfill_items
                        WHERE job_id=? AND status='succeeded'
                    ),
                    failed_instruments=(
                        SELECT COUNT(*) FROM market_daily_backfill_items
                        WHERE job_id=? AND status='failed'
                    ),
                    retryable_failed_instruments=0,
                    average_quality_score=(
                        SELECT AVG(quality_score) FROM market_daily_backfill_items
                        WHERE job_id=? AND status='succeeded'
                    ),
                    stored_bars=(
                        SELECT COALESCE(SUM(stored_bars),0) FROM market_daily_backfill_items
                        WHERE job_id=?
                    ),
                    current_code=NULL, last_error=NULL, failure_details_json='[]',
                    cancel_requested=0, lease_owner=NULL, lease_expires_at=NULL,
                    started_at=NULL, completed_at=NULL, updated_at=?
                WHERE job_id=?
                """,
                (job_id, job_id, job_id, job_id, job_id, now, job_id),
            )

    async def cancel(self, job_id: str) -> MarketDailyBackfillJob:
        await self.initialize()
        changed = await asyncio.to_thread(self._cancel, job_id)
        if not changed:
            job = await self.get(job_id)
            if job.status not in {"pending", "running"}:
                return job
        return await self.get(job_id)

    def _cancel(self, job_id: str) -> bool:
        now = _iso()
        with self.repository._connect() as connection:
            result = connection.execute(
                """
                UPDATE market_daily_backfill_jobs
                SET cancel_requested=1,
                    status=CASE WHEN status='pending' THEN 'cancelled' ELSE status END,
                    completed_at=CASE WHEN status='pending' THEN ? ELSE completed_at END,
                    updated_at=?
                WHERE job_id=? AND status IN ('pending','running')
                """,
                (now, now, job_id),
            )
        return result.rowcount == 1

    def _claim_job(self) -> dict | None:
        now = _utc_now()
        now_text = _iso(now)
        lease = _iso(now + timedelta(seconds=_LEASE_SECONDS))
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM market_daily_backfill_jobs
                WHERE status='pending'
                   OR (status='running' AND lease_expires_at<?)
                ORDER BY created_at LIMIT 1
                """,
                (now_text,),
            ).fetchone()
            if row is None:
                return None
            job_id = row["job_id"]
            connection.execute(
                """
                UPDATE market_daily_backfill_jobs
                SET status='running', started_at=COALESCE(started_at, ?),
                    lease_owner=?, lease_expires_at=?, updated_at=?
                WHERE job_id=?
                """,
                (now_text, self._worker_id, lease, now_text, job_id),
            )
            connection.execute(
                "UPDATE market_daily_backfill_items SET status='pending' WHERE job_id=? AND status='running'",
                (job_id,),
            )
            claimed = connection.execute(
                "SELECT * FROM market_daily_backfill_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return dict(claimed)

    def _claim_item(self, job_id: str) -> dict | None:
        now = _iso()
        lease = _iso(_utc_now() + timedelta(seconds=_LEASE_SECONDS))
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = connection.execute(
                "SELECT cancel_requested FROM market_daily_backfill_jobs WHERE job_id=? AND lease_owner=?",
                (job_id, self._worker_id),
            ).fetchone()
            if job is None or job["cancel_requested"]:
                return None
            row = connection.execute(
                "SELECT * FROM market_daily_backfill_items WHERE job_id=? AND status='pending' ORDER BY code LIMIT 1",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE market_daily_backfill_items SET status='running', attempts=attempts+1, updated_at=? WHERE job_id=? AND code=?",
                (now, job_id, row["code"]),
            )
            connection.execute(
                "UPDATE market_daily_backfill_jobs SET current_code=?, lease_expires_at=?, updated_at=? WHERE job_id=?",
                (row["code"], lease, now, job_id),
            )
        return dict(row)

    def _finish_item(
        self,
        job_id: str,
        code: str,
        *,
        stored: int,
        source: str | None,
        quality_score: float | None = None,
        validation: dict[str, object] | None = None,
        failure_kind: str | None = None,
        error: str | None,
    ) -> None:
        now = _iso()
        status = "failed" if error else "succeeded"
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE market_daily_backfill_items
                SET status=?, stored_bars=?, source=?, quality_score=?, validation_json=?,
                    failure_kind=?, last_error=?, updated_at=?
                WHERE job_id=? AND code=? AND status='running'
                """,
                (
                    status, stored, source, quality_score,
                    json.dumps(validation, ensure_ascii=False) if validation is not None else None,
                    failure_kind, error[:1000] if error else None, now, job_id, code,
                ),
            )
            failures = [
                {
                    "code": row["code"],
                    "kind": row["failure_kind"] or _FAILURE_INVALID,
                    "retryable": row["failure_kind"] in _RETRYABLE_FAILURE_KINDS,
                    "error": row["last_error"],
                }
                for row in connection.execute(
                    """
                    SELECT code,failure_kind,last_error FROM market_daily_backfill_items
                    WHERE job_id=? AND status='failed' ORDER BY code LIMIT ?
                    """,
                    (job_id, _FAILURE_DETAIL_LIMIT),
                ).fetchall()
            ]
            connection.execute(
                """
                UPDATE market_daily_backfill_jobs SET
                    completed_instruments=(SELECT COUNT(*) FROM market_daily_backfill_items WHERE job_id=? AND status IN ('succeeded','failed','skipped')),
                    succeeded_instruments=(SELECT COUNT(*) FROM market_daily_backfill_items WHERE job_id=? AND status='succeeded'),
                    failed_instruments=(SELECT COUNT(*) FROM market_daily_backfill_items WHERE job_id=? AND status='failed'),
                    retryable_failed_instruments=(
                        SELECT COUNT(*) FROM market_daily_backfill_items
                        WHERE job_id=? AND status='failed' AND failure_kind='upstream_unavailable'
                    ),
                    average_quality_score=(
                        SELECT AVG(quality_score) FROM market_daily_backfill_items
                        WHERE job_id=? AND status='succeeded'
                    ),
                    stored_bars=(SELECT COALESCE(SUM(stored_bars),0) FROM market_daily_backfill_items WHERE job_id=?),
                    failure_details_json=?, last_error=COALESCE(?, last_error), updated_at=?
                WHERE job_id=? AND lease_owner=?
                """,
                (
                    job_id, job_id, job_id, job_id, job_id, job_id,
                    json.dumps(failures, ensure_ascii=False),
                    error[:1000] if error else None, now, job_id, self._worker_id,
                ),
            )

    def _complete_job(self, job_id: str) -> None:
        now = _iso()
        with self.repository._connect() as connection:
            row = connection.execute(
                "SELECT cancel_requested,failed_instruments,total_instruments FROM market_daily_backfill_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            if row["cancel_requested"]:
                status = "cancelled"
            elif row["failed_instruments"] > 0:
                status = "failed"
            else:
                status = "succeeded"
            connection.execute(
                """
                UPDATE market_daily_backfill_jobs
                SET status=?, current_code=NULL, completed_at=?, updated_at=?,
                    lease_owner=NULL, lease_expires_at=NULL
                WHERE job_id=? AND lease_owner=?
                """,
                (status, now, now, job_id, self._worker_id),
            )

    async def _process_item(self, job: dict, item: dict) -> None:
        job_id = str(job["job_id"])
        code = str(item["code"])
        try:
            candidates = await get_historical_bar_candidates(
                code,
                date.fromisoformat(job["start_date"]),
                date.fromisoformat(job["end_date"]),
                period="daily",
                adjust="",
                max_provider_sources=int(job["max_provider_sources"]),
                max_successes=3,
                request_limiter=self._limiter,
            )
            validated = _select_validated_candidate(candidates)
            records = _records_from_history(code, str(item["name"]), validated.primary)
            if not records:
                raise ValueError("指定区间没有历史日线")
            stored = await asyncio.to_thread(
                self.repository.upsert_historical_bars,
                records,
                overwrite_existing=bool(job["overwrite_existing"]),
            )
            await asyncio.to_thread(
                self._finish_item,
                job_id,
                code,
                stored=stored,
                source=validated.primary.source,
                quality_score=validated.score,
                validation=validated.details,
                error=None,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # 单票失败不终止全市场任务
            logger.warning("历史日线回填单票失败: job=%s code=%s", job_id, code, exc_info=True)
            await asyncio.to_thread(
                self._finish_item,
                job_id,
                code,
                stored=0,
                source=None,
                failure_kind=_failure_kind(error),
                error=str(error) or type(error).__name__,
            )

    async def _process_job(self, job: dict) -> None:
        job_id = str(job["job_id"])

        async def worker() -> None:
            while item := await asyncio.to_thread(self._claim_item, job_id):
                await self._process_item(job, item)

        await asyncio.gather(*(worker() for _ in range(_WORKER_CONCURRENCY)))
        await asyncio.to_thread(self._complete_job, job_id)

    async def run_worker(self) -> None:
        await self.initialize()
        while True:
            job = await asyncio.to_thread(self._claim_job)
            if job is None:
                await asyncio.sleep(2)
                continue
            await self._process_job(job)


market_daily_backfill_service = MarketDailyBackfillService()
