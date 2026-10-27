"""Workflow 事件批量入库与微批刷新器的行为契约。"""

import asyncio
import sqlite3
import time

import pytest

from app.infrastructure.persistence.ddl import (
    WORKFLOW_ACTIVE_USER_INDEX,
    WORKFLOW_JOB_STATEMENTS,
)
from app.infrastructure.persistence.workflow_jobs import WorkflowJobStore, WorkflowLeaseLostError
from app.runtime.workflow_worker import _WorkflowEventBatcher


@pytest.fixture()
def store() -> WorkflowJobStore:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    for statement in (*WORKFLOW_JOB_STATEMENTS, WORKFLOW_ACTIVE_USER_INDEX):
        connection.execute(statement)
    return WorkflowJobStore(lambda: connection)


async def _claim_running_job(store: WorkflowJobStore, owner: str = "w1"):
    submission = store.submit_or_attach(
        "analysis",
        user_id=1,
        dedupe_key="600519",
        request={"code": "600519"},
        max_attempts=2,
    )
    claimed = store.claim_next(owner, lease_seconds=900, now=time.time())
    assert claimed is not None and claimed.id == submission.job.id
    return submission.job


def _event_types(store: WorkflowJobStore, job_id: str) -> list[tuple[int, str]]:
    return [
        (event.sequence, event.event_type)
        for event in store.list_events(job_id, user_id=1, attempt=1, after_sequence=0)
    ]


async def test_append_events_persists_ordered_rows(store: WorkflowJobStore) -> None:
    job = await _claim_running_job(store)
    persisted = store.append_events(
        job.id,
        "w1",
        [("stage_started", {"index": 1}), ("stage_completed", {"index": 2})],
    )
    assert [event.sequence for event in persisted] == [1, 2]
    assert _event_types(store, job.id) == [(1, "stage_started"), (2, "stage_completed")]


async def test_append_events_requires_live_lease(store: WorkflowJobStore) -> None:
    job = await _claim_running_job(store)
    store.cancel(job.id, user_id=1, event_payload={"type": "error", "cancelled": True})
    with pytest.raises(WorkflowLeaseLostError):
        store.append_events(job.id, "w1", [("stage_started", {"index": 1})])


async def test_batcher_flushes_pending_events_after_silence(store: WorkflowJobStore) -> None:
    job = await _claim_running_job(store)
    batcher = _WorkflowEventBatcher(job.id, "w1", store=store)
    await batcher.emit({"type": "stage_started", "index": 1})
    await batcher.emit({"type": "stage_completed", "index": 1})
    assert _event_types(store, job.id) == []
    await asyncio.sleep(0.35)
    assert _event_types(store, job.id) == [(1, "stage_started"), (2, "stage_completed")]
    await batcher.close()


async def test_batcher_flushes_immediately_when_batch_is_full(store: WorkflowJobStore) -> None:
    job = await _claim_running_job(store)
    batcher = _WorkflowEventBatcher(job.id, "w1", store=store)
    for index in range(20):
        await batcher.emit({"type": "stage_progress", "index": index})
    sequences = [sequence for sequence, _ in _event_types(store, job.id)]
    assert sequences == list(range(1, 21))
    await batcher.close()


async def test_batcher_surfaces_lease_loss_on_next_emit_and_close(store: WorkflowJobStore) -> None:
    job = await _claim_running_job(store)
    batcher = _WorkflowEventBatcher(job.id, "w1", store=store)
    await batcher.emit({"type": "stage_started", "index": 1})
    store.cancel(job.id, user_id=1, event_payload={"type": "error", "cancelled": True})
    await asyncio.sleep(0.35)
    with pytest.raises(WorkflowLeaseLostError):
        await batcher.emit({"type": "stage_progress", "index": 2})
    with pytest.raises(WorkflowLeaseLostError):
        await batcher.close()
