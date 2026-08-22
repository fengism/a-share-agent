from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from app.configuration import get_settings
from app.core.concurrency.durable_stream import stream_durable_workflow_events
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.metrics import metrics
from app.domain.industry_chain import IndustryChainResearchScope, resolve_industry_chain_scope
from app.infrastructure.persistence.workflow_jobs import (
    WorkflowJob,
    WorkflowQueueFullError,
    workflow_job_store,
)
from app.modules.workflow.models import (
    WorkflowCapacityError,
    WorkflowExecutionError,
    WorkflowJobSnapshot,
    WorkflowKind,
    WorkflowSubmissionSnapshot,
)

_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _industry_today():
    return datetime.now(_MARKET_TIMEZONE).date()


def _snapshot(job: WorkflowJob) -> WorkflowJobSnapshot:
    return WorkflowJobSnapshot(
        id=job.id,
        kind=job.kind,
        user_id=job.user_id,
        dedupe_key=job.dedupe_key,
        request=job.request,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        available_at=job.available_at,
        last_error=job.last_error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


async def submit_workflow(
    kind: WorkflowKind,
    *,
    user_id: int,
    dedupe_key: str,
    request: dict[str, Any],
) -> WorkflowSubmissionSnapshot:
    settings = get_settings()
    try:
        submission = await call_blocking(
            workflow_job_store.submit_or_attach,
            kind,
            user_id=user_id,
            dedupe_key=dedupe_key,
            request=request,
            max_attempts=settings.workflow_job_max_attempts,
            max_active_per_user=settings.workflow_job_max_active_per_user,
            max_active_total=settings.workflow_job_max_active_total,
            semaphore=database_semaphore,
        )
    except WorkflowQueueFullError as error:
        raise WorkflowCapacityError(error.scope, error.limit) from error
    metrics.record_workflow_event(kind, "attached" if submission.attached else "submitted")
    return WorkflowSubmissionSnapshot(job=_snapshot(submission.job), attached=submission.attached)


async def submit_analysis_workflow(code: str, user_id: int) -> WorkflowSubmissionSnapshot:
    return await submit_workflow(
        "analysis",
        user_id=user_id,
        dedupe_key=code,
        request={"code": code},
    )


async def submit_industry_chain_workflow(
    name: str,
    user_id: int,
    scope: IndustryChainResearchScope | dict[str, Any] | None = None,
) -> WorkflowSubmissionSnapshot:
    validated_scope = scope if isinstance(scope, IndustryChainResearchScope) else IndustryChainResearchScope.model_validate(scope or {})
    resolved_scope = resolve_industry_chain_scope(validated_scope, today=_industry_today())
    scope_payload = resolved_scope.model_dump(mode="json")
    scope_digest = hashlib.sha256(
        json.dumps(scope_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return await submit_workflow(
        "industry_chain",
        user_id=user_id,
        dedupe_key=f"{name}:{scope_digest}",
        request={"name": name, "scope": scope_payload},
    )


async def submit_daily_review_workflow(request: dict[str, Any], user_id: int) -> WorkflowSubmissionSnapshot:
    date_text = str(request.get("date") or _industry_today().isoformat())
    payload = {"date": date_text, "force": bool(request.get("force", False))}
    return await submit_workflow(
        "daily_review",
        user_id=user_id,
        dedupe_key=date_text,
        request=payload,
    )


async def submit_screener_strategy_workflow(request: dict[str, Any], user_id: int) -> WorkflowSubmissionSnapshot:
    payload = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return await submit_workflow(
        "screener_strategy",
        user_id=user_id,
        dedupe_key=hashlib.sha256(payload.encode()).hexdigest(),
        request=request,
    )


async def get_workflow(job_id: str, user_id: int) -> WorkflowJobSnapshot | None:
    job = await call_blocking(
        workflow_job_store.get,
        job_id,
        user_id=user_id,
        semaphore=database_semaphore,
    )
    return _snapshot(job) if job is not None else None


def _cancel_payload(job: WorkflowJobSnapshot) -> dict[str, Any]:
    if job.kind == "analysis":
        return {"type": "error", "error": "分析已取消", "cancelled": True}
    if job.kind == "screener_strategy":
        return {"type": "error", "message": "策略选股已取消", "cancelled": True}
    if job.kind == "daily_review":
        return {"type": "error", "message": "每日复盘已取消", "cancelled": True}
    return {
        "type": "error",
        "stage": "error",
        "message": "产业链分析已取消",
        "cancelled": True,
    }


async def cancel_workflow(job_id: str, user_id: int) -> WorkflowJobSnapshot | None:
    current = await get_workflow(job_id, user_id)
    if current is None:
        return None
    cancelled = await call_blocking(
        workflow_job_store.cancel,
        job_id,
        user_id=user_id,
        event_payload=_cancel_payload(current),
        semaphore=database_semaphore,
    )
    if cancelled is not None and cancelled.status == "cancelled":
        metrics.record_workflow_event(cancelled.kind, "cancelled")
    return _snapshot(cancelled) if cancelled is not None else None


def _parse_event_cursor(last_event_id: str | None) -> tuple[int, int]:
    if not last_event_id:
        return 0, 0
    try:
        attempt_text, sequence_text = last_event_id.split(":", maxsplit=1)
        attempt = int(attempt_text)
        sequence = int(sequence_text)
    except (TypeError, ValueError):
        return 0, 0
    return max(0, attempt), max(0, sequence)


async def create_workflow_event_generator(
    job_id: str,
    user_id: int,
    *,
    last_event_id: str | None = None,
) -> AsyncGenerator[dict, None] | None:
    initial = await get_workflow(job_id, user_id)
    if initial is None:
        return None
    settings = get_settings()

    async def load_job():
        return await call_blocking(
            workflow_job_store.get,
            job_id,
            user_id=user_id,
            semaphore=database_semaphore,
        )

    async def load_events(attempt: int, after_sequence: int):
        return await call_blocking(
            workflow_job_store.list_events,
            job_id,
            user_id=user_id,
            attempt=attempt,
            after_sequence=after_sequence,
            semaphore=database_semaphore,
        )

    attempt, sequence = _parse_event_cursor(last_event_id)
    return cast(AsyncGenerator[dict, None], stream_durable_workflow_events(
        load_job=load_job,
        load_events=load_events,
        poll_seconds=min(0.5, settings.workflow_job_poll_seconds),
        keepalive_seconds=settings.chat_heartbeat_seconds,
        workflow_kind=initial.kind,
        start_attempt=attempt,
        after_sequence=sequence,
    ))


async def wait_for_workflow_result(
    job_id: str,
    user_id: int,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    current_attempt = 0
    last_sequence = 0
    while time.monotonic() < deadline:
        job = await get_workflow(job_id, user_id)
        if job is None:
            raise WorkflowExecutionError("任务不存在或已清理")
        if job.attempts != current_attempt:
            current_attempt = job.attempts
            last_sequence = 0
        events = await call_blocking(
            workflow_job_store.list_events,
            job_id,
            user_id=user_id,
            attempt=current_attempt,
            after_sequence=last_sequence,
            semaphore=database_semaphore,
        )
        for event in events:
            last_sequence = event.sequence
            event_type = event.payload.get("type")
            if event_type in {"complete", "cached"} and isinstance(event.payload.get("result"), dict):
                return cast(dict[str, Any], event.payload["result"])
            if event_type == "error":
                raise WorkflowExecutionError(
                    str(event.payload.get("error") or event.payload.get("message") or "任务执行失败"),
                    cancelled=bool(event.payload.get("cancelled")),
                )
        if job.status == "cancelled":
            raise WorkflowExecutionError("任务已取消", cancelled=True)
        if job.status == "failed":
            raise WorkflowExecutionError(job.last_error or "任务执行失败")
        if job.status == "succeeded":
            raise WorkflowExecutionError("任务已完成但未找到结果事件")
        await asyncio.sleep(min(0.5, get_settings().workflow_job_poll_seconds))
    raise WorkflowExecutionError("等待任务完成超时")


__all__ = [
    "cancel_workflow",
    "create_workflow_event_generator",
    "get_workflow",
    "submit_analysis_workflow",
    "submit_daily_review_workflow",
    "submit_industry_chain_workflow",
    "submit_screener_strategy_workflow",
    "submit_workflow",
    "wait_for_workflow_result",
]
