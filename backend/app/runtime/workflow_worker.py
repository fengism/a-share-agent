"""Analysis、Industry Chain 与 Screener Strategy Workflow Job 执行器。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, cast

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.metrics import metrics
from app.core.request_context import (
    bind_settings_cache,
    reset_current_user,
    reset_settings_cache,
    set_current_user,
)
from app.domain.identity import UserRecord
from app.infrastructure.llm.policy import is_llm_failure
from app.infrastructure.persistence.workflow_jobs import (
    WorkflowJob,
    WorkflowJobStore,
    WorkflowLeaseLostError,
    workflow_job_store,
)
from app.modules.analysis.public import run_analysis
from app.modules.analysis.result_service import AnalysisArchiveError
from app.modules.daily_review.public import DailyReviewRequest, generate_daily_review
from app.modules.industry_chain.public import IndustryChainResearchScope, run_industry_chain_analysis
from app.modules.screener.public import ScreenerStrategyRequest, screen_candidates_by_strategy

logger = logging.getLogger(__name__)
_SHUTDOWN_CANCEL_MESSAGE = "服务关闭，任务已取消"

_EVENT_BATCH_MAX_EVENTS = 20
_EVENT_BATCH_MAX_DELAY_SECONDS = 0.15


class _WorkflowEventBatcher:
    """把进度事件微批聚合后单事务入库，显著降低长任务的 SQLite 写事务数。

    事件顺序严格保持；满批（_EVENT_BATCH_MAX_EVENTS）或静默超时
    （_EVENT_BATCH_MAX_DELAY_SECONDS）即 flush。终态事件（error/complete）
    不经过这里，仍由 worker 在任务结束时一次性写入。持久化失败（如用户
    取消导致租约失效）保存在 _failure，在下次 emit/flush/close 时重抛，
    保证管线与 worker 及时感知并中止。
    """

    def __init__(
        self,
        job_id: str,
        owner_id: str,
        store: WorkflowJobStore = workflow_job_store,
    ) -> None:
        self.job_id = job_id
        self._owner_id = owner_id
        self._store = store
        self._pending: list[tuple[str, dict[str, Any]]] = []
        self._signal = asyncio.Event()
        self._flusher: asyncio.Task[None] | None = None
        self._failure: BaseException | None = None
        self._closed = False

    async def emit(self, event: Any) -> None:
        if self._failure is not None:
            raise self._failure
        payload = event if isinstance(event, dict) else event.model_dump(mode="json")
        self._pending.append((str(payload.get("type")), payload))
        if len(self._pending) >= _EVENT_BATCH_MAX_EVENTS:
            await self.flush()
            return
        if self._flusher is None:
            self._signal.set()
            self._flusher = asyncio.create_task(self._flush_after_delay())
        else:
            self._signal.set()

    async def flush(self) -> None:
        if self._failure is not None:
            raise self._failure
        await self._drain()

    async def close(self) -> None:
        self._closed = True
        self._signal.set()
        flusher = self._flusher
        if flusher is not None:
            try:
                await flusher
            except asyncio.CancelledError:
                pass
        if self._failure is not None:
            raise self._failure
        await self._drain()

    async def _flush_after_delay(self) -> None:
        try:
            while True:
                self._signal.clear()
                try:
                    await asyncio.wait_for(self._signal.wait(), timeout=_EVENT_BATCH_MAX_DELAY_SECONDS)
                except TimeoutError:
                    pass
                if self._pending:
                    await self._drain()
                if self._closed:
                    return
        except asyncio.CancelledError:
            raise
        except BaseException as error:  # noqa: BLE001 - 转存失败，由 emit/flush/close 重抛
            self._failure = error
        finally:
            self._flusher = None

    async def _drain(self) -> None:
        if not self._pending:
            return
        events = self._pending
        self._pending = []
        try:
            await call_blocking(
                self._store.append_events,
                self.job_id,
                self._owner_id,
                events,
                semaphore=database_semaphore,
            )
        except BaseException:
            self._pending = [*events, *self._pending]
            raise


async def _safe_flush(batcher: _WorkflowEventBatcher) -> None:
    """失败/取消路径尽力保留已产生的进度事件；租约已失效则静默放弃。"""
    try:
        await batcher.flush()
    except Exception:
        logger.debug("Workflow 进度事件刷写失败: job_id=%s", batcher.job_id, exc_info=True)


async def _renew_workflow_lease(job_id: str, owner_id: str, lease_seconds: float) -> None:
    interval = min(5.0, max(1.0, lease_seconds / 3))
    while True:
        await asyncio.sleep(interval)
        renewed = await call_blocking(
            workflow_job_store.renew_lease,
            job_id,
            owner_id,
            lease_seconds=lease_seconds,
            semaphore=database_semaphore,
        )
        if not renewed:
            raise WorkflowLeaseLostError(f"Workflow Job 租约续期失败: job_id={job_id} owner={owner_id}")


def _terminal_error_payload(job: WorkflowJob, error_payload: dict[str, Any] | None) -> dict[str, Any]:
    if error_payload is not None:
        return error_payload
    if job.kind == "analysis":
        return {"type": "error", "error": "分析失败，请稍后重试"}
    if job.kind == "screener_strategy":
        return {"type": "error", "message": "策略选股失败，请稍后重试"}
    if job.kind == "daily_review":
        return {"type": "error", "message": "每日复盘生成失败，请稍后重试"}
    return {"type": "error", "stage": "error", "message": "产业链分析失败，请稍后重试"}


def _shutdown_cancel_payload(job: WorkflowJob) -> dict[str, Any]:
    if job.kind == "analysis":
        return {"type": "error", "error": _SHUTDOWN_CANCEL_MESSAGE, "cancelled": True}
    if job.kind in {"screener_strategy", "daily_review"}:
        return {"type": "error", "message": _SHUTDOWN_CANCEL_MESSAGE, "cancelled": True}
    return {
        "type": "error",
        "stage": "error",
        "message": _SHUTDOWN_CANCEL_MESSAGE,
        "cancelled": True,
    }


async def process_next_workflow_job(
    owner_id: str,
    *,
    shutdown_event: asyncio.Event | None = None,
) -> bool:
    settings = get_settings()
    job = await call_blocking(
        workflow_job_store.claim_next,
        owner_id,
        lease_seconds=settings.workflow_job_lease_seconds,
        max_running_per_user=settings.workflow_job_max_running_per_user,
        semaphore=database_semaphore,
    )
    if job is None:
        return False
    metrics.record_workflow_event(job.kind, "claimed")
    started_at = time.perf_counter()

    deferred_error: dict[str, Any] | None = None
    deferred_complete: dict[str, Any] | None = None
    batcher = _WorkflowEventBatcher(job.id, owner_id)

    async def emit(event) -> None:
        nonlocal deferred_complete, deferred_error
        payload = event if isinstance(event, dict) else event.model_dump(mode="json")
        event_type = payload.get("type")
        if event_type == "error":
            deferred_error = payload
            return
        if event_type == "complete":
            deferred_complete = payload
            return
        await batcher.emit(event)

    async def ensure_job_owned() -> None:
        owned = await call_blocking(
            workflow_job_store.owns_running_job,
            job.id,
            owner_id,
            semaphore=database_semaphore,
        )
        if not owned:
            raise WorkflowLeaseLostError(f"Workflow Job 已取消或租约失效: {job.id}")

    async def execute() -> None:
        if job.kind == "analysis":
            await run_analysis(
                str(job.request["code"]),
                job.user_id,
                progress_callback=emit,
                force=bool(job.request.get("force", False)),
                before_persist=ensure_job_owned,
            )
        elif job.kind == "industry_chain":
            scope = IndustryChainResearchScope.model_validate(job.request.get("scope") or {})
            await run_industry_chain_analysis(
                str(job.request["name"]),
                job.user_id,
                scope=scope,
                force=bool(job.request.get("force", False)),
                progress_callback=emit,
                before_persist=ensure_job_owned,
            )
        elif job.kind == "screener_strategy":
            result = await screen_candidates_by_strategy(ScreenerStrategyRequest.model_validate(job.request), emit)
            await emit({"type": "complete", "result": result.model_dump(mode="json")})
        elif job.kind == "daily_review":
            result = await generate_daily_review(
                DailyReviewRequest.model_validate(job.request),
                job.user_id,
                progress_callback=emit,
            )
            await emit({"type": "complete", "result": result.model_dump(mode="json")})
        else:
            raise ValueError(f"不支持的 Workflow 类型: {job.kind}")

    async def execute_with_user_context() -> None:
        workflow_user = cast(UserRecord, {
            "id": job.user_id,
            "username": f"workflow-user-{job.user_id}",
            "is_admin": False,
            "password_hash": "",
        })
        user_token = set_current_user(workflow_user)
        settings_token = bind_settings_cache()
        try:
            await execute()
        finally:
            reset_settings_cache(settings_token)
            reset_current_user(user_token)

    execution = asyncio.create_task(
        execute_with_user_context(),
        name=f"workflow_job_execution:{job.id}",
    )
    heartbeat = asyncio.create_task(
        _renew_workflow_lease(job.id, owner_id, settings.workflow_job_lease_seconds),
        name=f"workflow_job_lease:{job.id}",
    )
    try:
        done, _ = await asyncio.wait(
            {execution, heartbeat},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat in done and execution not in done:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            heartbeat.result()
            raise WorkflowLeaseLostError(f"Workflow Job 租约任务意外结束: {job.id}")
        await execution
        await batcher.flush()
        completed = await call_blocking(
            workflow_job_store.complete,
            job.id,
            owner_id,
            completion_event=("complete", deferred_complete) if deferred_complete is not None else None,
            semaphore=database_semaphore,
        )
        if not completed:
            logger.info("Workflow Job 租约失效，丢弃完成状态: job_id=%s", job.id)
            metrics.record_workflow_event(job.kind, "lease_lost")
        else:
            duration_ms = (time.perf_counter() - started_at) * 1000
            metrics.record_workflow_event(job.kind, "completed")
            metrics.record_workflow_run(
                job.kind,
                success=True,
                duration_ms=duration_ms,
            )
            logger.info(
                "Workflow Job 执行完成: job_id=%s kind=%s duration_ms=%.0f",
                job.id,
                job.kind,
                duration_ms,
            )
    except WorkflowLeaseLostError as error:
        metrics.record_workflow_event(job.kind, "lease_lost")
        logger.info("Workflow Job 已停止执行: job_id=%s reason=%s", job.id, error)
    except asyncio.CancelledError:
        execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        await _safe_flush(batcher)
        if shutdown_event is not None and shutdown_event.is_set():
            cancelled = await call_blocking(
                workflow_job_store.cancel_owned,
                job.id,
                owner_id,
                event_payload=_shutdown_cancel_payload(job),
                reason=_SHUTDOWN_CANCEL_MESSAGE,
                semaphore=database_semaphore,
            )
            if cancelled:
                metrics.record_workflow_event(job.kind, "cancelled")
                logger.info("服务关闭，Workflow Job 已取消: job_id=%s kind=%s", job.id, job.kind)
        else:
            await call_blocking(
                workflow_job_store.release,
                job.id,
                owner_id,
                "CancelledError",
                semaphore=database_semaphore,
            )
            metrics.record_workflow_event(job.kind, "released")
        raise
    except Exception as error:
        await _safe_flush(batcher)
        allow_retry = not is_llm_failure(error) and not isinstance(error, AnalysisArchiveError)
        terminal_event = (
            "error",
            _terminal_error_payload(job, deferred_error),
        ) if not allow_retry or job.attempts >= job.max_attempts else None
        retry_delay = settings.workflow_job_retry_base_seconds * (2 ** max(0, job.attempts - 1))
        status = await call_blocking(
            workflow_job_store.fail,
            job.id,
            owner_id,
            type(error).__name__,
            retry_delay_seconds=retry_delay,
            allow_retry=allow_retry,
            terminal_event=terminal_event,
            semaphore=database_semaphore,
        )
        if status is None:
            metrics.record_workflow_event(job.kind, "lease_lost")
            logger.info(
                "Workflow Job 租约失效，丢弃失败状态: job_id=%s kind=%s",
                job.id,
                job.kind,
            )
        else:
            metrics.record_workflow_event(job.kind, "retrying" if status == "pending" else "failed")
            metrics.record_workflow_run(
                job.kind,
                success=False,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error_type=type(error).__name__,
            )
            logger.exception(
                "Workflow Job 执行失败: job_id=%s kind=%s attempt=%s status=%s",
                job.id,
                job.kind,
                job.attempts,
                status,
            )
    finally:
        execution.cancel()
        heartbeat.cancel()
        await asyncio.gather(execution, heartbeat, return_exceptions=True)
        try:
            await batcher.close()
        except Exception:
            logger.debug("Workflow 事件批量刷写收尾失败: job_id=%s", job.id, exc_info=True)
    return True


__all__ = ["process_next_workflow_job"]
