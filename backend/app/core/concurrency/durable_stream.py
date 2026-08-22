"""将持久化 Workflow 事件适配为 SSE 事件流。"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, Protocol

from app.core.metrics import metrics


class WorkflowJobSnapshot(Protocol):
    status: str
    attempts: int


class WorkflowEventSnapshot(Protocol):
    sequence: int
    event_type: str
    payload: dict[str, Any]


JobLoader = Callable[[], Awaitable[WorkflowJobSnapshot | None]]
EventLoader = Callable[[int, int], Awaitable[list[WorkflowEventSnapshot]]]


async def stream_durable_workflow_events(
    *,
    load_job: JobLoader,
    load_events: EventLoader,
    poll_seconds: float = 0.25,
    keepalive_seconds: float = 15.0,
    workflow_kind: str = "workflow",
    start_attempt: int = 0,
    after_sequence: int = 0,
) -> AsyncGenerator[dict, None]:
    """按 attempt/sequence 顺序回放事件，并在等待期间发送 SSE keepalive。"""
    metrics.adjust_workflow_streams(workflow_kind, 1)
    metrics.record_workflow_event(workflow_kind, "stream_opened")
    try:
        current_attempt = max(0, start_attempt)
        last_sequence = max(0, after_sequence)
        last_emit_at = time.monotonic()

        while True:
            job = await load_job()
            if job is None:
                return
            if job.attempts != current_attempt:
                current_attempt = job.attempts
                last_sequence = 0

            events = await load_events(current_attempt, last_sequence)
            for event in events:
                last_sequence = event.sequence
                last_emit_at = time.monotonic()
                yield {
                    "id": f"{current_attempt}:{event.sequence}",
                    "event": event.event_type,
                    "data": json.dumps(event.payload, ensure_ascii=False, default=str),
                }

            if job.status in {"succeeded", "failed", "cancelled"}:
                return

            if time.monotonic() - last_emit_at >= keepalive_seconds:
                last_emit_at = time.monotonic()
                yield {"comment": "keepalive"}
            await asyncio.sleep(max(0.01, poll_seconds))
    finally:
        metrics.adjust_workflow_streams(workflow_kind, -1)
        metrics.record_workflow_event(workflow_kind, "stream_closed")


__all__ = ["stream_durable_workflow_events"]
