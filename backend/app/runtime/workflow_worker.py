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
from app.infrastructure.persistence.workflow_jobs import (
    WorkflowJob,
    WorkflowLeaseLostError,
    workflow_job_store,
)
from app.modules.analysis.public import run_analysis
from app.modules.daily_review.public import DailyReviewRequest, generate_daily_review
from app.modules.industry_chain.public import IndustryChainResearchScope, run_industry_chain_analysis
from app.modules.screener.public import ScreenerStrategyRequest, screen_candidates_by_strategy

logger = logging.getLogger(__name__)


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


async def process_next_workflow_job(owner_id: str) -> bool:
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

    async def emit(event) -> None:
        nonlocal deferred_error
        payload = event if isinstance(event, dict) else event.model_dump(mode="json")
        event_type = payload.get("type")
        if event_type == "error":
            deferred_error = payload
            return
        await call_blocking(
            workflow_job_store.append_event,
            job.id,
            owner_id,
            str(event_type),
            payload,
            semaphore=database_semaphore,
        )

    async def execute() -> None:
        if job.kind == "analysis":
            await run_analysis(str(job.request["code"]), job.user_id, progress_callback=emit)
        elif job.kind == "industry_chain":
            scope = IndustryChainResearchScope.model_validate(job.request.get("scope") or {})
            await run_industry_chain_analysis(
                str(job.request["name"]),
                job.user_id,
                scope=scope,
                progress_callback=emit,
            )
        elif job.kind == "screener_strategy":
            result = await screen_candidates_by_strategy(ScreenerStrategyRequest.model_validate(job.request), emit)
            await emit({"type": "complete", "result": result.model_dump(mode="json")})
        elif job.kind == "daily_review":
            await emit({"type": "stage_started", "stage": "generate", "message": "正在生成每日复盘"})
            result = await generate_daily_review(DailyReviewRequest.model_validate(job.request), job.user_id)
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
        if heartbeat in done:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            heartbeat.result()
            raise WorkflowLeaseLostError(f"Workflow Job 租约任务意外结束: {job.id}")
        await execution
        completed = await call_blocking(
            workflow_job_store.complete,
            job.id,
            owner_id,
            semaphore=database_semaphore,
        )
        if not completed:
            logger.info("Workflow Job 租约失效，丢弃完成状态: job_id=%s", job.id)
            metrics.record_workflow_event(job.kind, "lease_lost")
        else:
            metrics.record_workflow_event(job.kind, "completed")
            metrics.record_workflow_run(
                job.kind,
                success=True,
                duration_ms=(time.perf_counter() - started_at) * 1000,
            )
    except WorkflowLeaseLostError as error:
        metrics.record_workflow_event(job.kind, "lease_lost")
        logger.info("Workflow Job 已停止执行: job_id=%s reason=%s", job.id, error)
    except asyncio.CancelledError:
        execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
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
        terminal = job.attempts >= job.max_attempts
        if terminal:
            payload = _terminal_error_payload(job, deferred_error)
            await call_blocking(
                workflow_job_store.append_event,
                job.id,
                owner_id,
                "error",
                payload,
                semaphore=database_semaphore,
            )
        retry_delay = settings.workflow_job_retry_base_seconds * (2 ** max(0, job.attempts - 1))
        status = await call_blocking(
            workflow_job_store.fail,
            job.id,
            owner_id,
            type(error).__name__,
            retry_delay_seconds=retry_delay,
            semaphore=database_semaphore,
        )
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
    return True


__all__ = ["process_next_workflow_job"]
