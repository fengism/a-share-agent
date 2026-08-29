"""Analysis 与 Industry Chain 共用的持久化 Workflow Job 状态机。"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import uuid4

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.infrastructure.persistence.ddl import WORKFLOW_ACTIVE_USER_INDEX, WORKFLOW_JOB_STATEMENTS
from app.infrastructure.persistence.leased_jobs import LeasedJobSpec, LeasedJobStateStore
from app.infrastructure.persistence.retention import PurgeResult

WorkflowKind = Literal["analysis", "industry_chain", "screener_strategy", "daily_review"]
WorkflowStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]
ConnectionProvider = Callable[[], sqlite3.Connection]


def _terminal_error_payload(kind: str, message: str) -> dict[str, Any]:
    if kind == "analysis":
        return {"type": "error", "error": message}
    if kind in {"screener_strategy", "daily_review"}:
        return {"type": "error", "message": message}
    return {"type": "error", "stage": "error", "message": message}

WORKFLOW_JOB_SCHEMA = ";\n".join(
    statement.strip() for statement in (*WORKFLOW_JOB_STATEMENTS, WORKFLOW_ACTIVE_USER_INDEX)
) + ";"


class WorkflowLeaseLostError(RuntimeError):
    pass


class WorkflowQueueFullError(RuntimeError):
    def __init__(self, scope: Literal["user", "global"], limit: int) -> None:
        super().__init__(f"Workflow active job limit reached: scope={scope} limit={limit}")
        self.scope = scope
        self.limit = limit


@dataclass(frozen=True, slots=True)
class WorkflowJob:
    id: str
    kind: WorkflowKind
    user_id: int
    dedupe_key: str
    request: dict[str, Any]
    status: WorkflowStatus
    attempts: int
    max_attempts: int
    available_at: float
    lease_owner: str | None
    lease_until: float | None
    last_error: str | None
    created_at: float
    updated_at: float
    completed_at: float | None


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    job_id: str
    attempt: int
    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: float


@dataclass(frozen=True, slots=True)
class WorkflowSubmission:
    job: WorkflowJob
    attached: bool


def _job_from_row(row: sqlite3.Row) -> WorkflowJob:
    return WorkflowJob(
        id=str(row["id"]),
        kind=row["kind"],
        user_id=int(row["user_id"]),
        dedupe_key=str(row["dedupe_key"]),
        request=json.loads(row["request_json"]),
        status=row["status"],
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        available_at=float(row["available_at"]),
        lease_owner=row["lease_owner"],
        lease_until=float(row["lease_until"]) if row["lease_until"] is not None else None,
        last_error=row["last_error"],
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        completed_at=float(row["completed_at"]) if row["completed_at"] is not None else None,
    )


class WorkflowRequestMismatchError(RuntimeError):
    """Active deduplicated job exists with an incompatible request payload."""


class WorkflowJobStore:
    def __init__(self, connection_provider: ConnectionProvider | None = None) -> None:
        self._connection_provider = connection_provider or (lambda: get_connection("user"))
        self._state = LeasedJobStateStore(
            LeasedJobSpec(
                table_name="workflow_jobs",
                terminal_statuses=("succeeded", "failed", "cancelled"),
            ),
            self._connection_provider,
        )

    def submit_or_attach(
        self,
        kind: WorkflowKind,
        *,
        user_id: int,
        dedupe_key: str,
        request: dict[str, Any],
        max_attempts: int,
        max_active_per_user: int | None = None,
        max_active_total: int | None = None,
        now: float | None = None,
    ) -> WorkflowSubmission:
        current_time = time.time() if now is None else now
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            active = connection.execute(
                """
                SELECT * FROM workflow_jobs
                WHERE kind = ? AND user_id = ? AND dedupe_key = ?
                  AND status IN ('pending', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (kind, user_id, dedupe_key),
            ).fetchone()
            if active is not None:
                active_job = _job_from_row(active)
                if kind in {"analysis", "daily_review"}:
                    active_request = {**active_job.request, "force": bool(active_job.request.get("force", False))}
                    if active_request != request:
                        raise WorkflowRequestMismatchError(
                            f"活动 Workflow 请求不兼容: kind={kind} dedupe_key={dedupe_key}"
                        )
                return WorkflowSubmission(active_job, attached=True)

            if max_active_per_user is not None:
                user_active = connection.execute(
                    """
                    SELECT COUNT(*) FROM workflow_jobs
                    WHERE user_id = ? AND status IN ('pending', 'running')
                    """,
                    (user_id,),
                ).fetchone()[0]
                if int(user_active) >= max(1, max_active_per_user):
                    raise WorkflowQueueFullError("user", max(1, max_active_per_user))

            if max_active_total is not None:
                total_active = connection.execute(
                    """
                    SELECT COUNT(*) FROM workflow_jobs
                    WHERE status IN ('pending', 'running')
                    """
                ).fetchone()[0]
                if int(total_active) >= max(1, max_active_total):
                    raise WorkflowQueueFullError("global", max(1, max_active_total))

            job_id = uuid4().hex
            connection.execute(
                """
                INSERT INTO workflow_jobs(
                    id, kind, user_id, dedupe_key, request_json, status,
                    attempts, max_attempts, available_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    user_id,
                    dedupe_key,
                    json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                    max(1, max_attempts),
                    current_time,
                    current_time,
                    current_time,
                ),
            )
            row = connection.execute("SELECT * FROM workflow_jobs WHERE id = ?", (job_id,)).fetchone()
            return WorkflowSubmission(_job_from_row(row), attached=False)

    def get(self, job_id: str, *, user_id: int) -> WorkflowJob | None:
        row = self._connection_provider().execute(
            "SELECT * FROM workflow_jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        ).fetchone()
        return _job_from_row(row) if row is not None else None

    def list_active(self, *, user_id: int) -> list[WorkflowJob]:
        rows = self._connection_provider().execute(
            """
            SELECT * FROM workflow_jobs
            WHERE user_id = ? AND status IN ('pending', 'running')
            ORDER BY updated_at DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [_job_from_row(row) for row in rows]

    def claim_next(
        self,
        owner_id: str,
        *,
        lease_seconds: float,
        max_running_per_user: int | None = None,
        now: float | None = None,
    ) -> WorkflowJob | None:
        current_time = time.time() if now is None else now
        self._expire_terminal_leases(current_time)
        if max_running_per_user is not None:
            row = self._claim_next_fair(
                owner_id,
                lease_seconds=lease_seconds,
                max_running_per_user=max_running_per_user,
                now=current_time,
            )
            return _job_from_row(row) if row is not None else None
        row = self._state.claim_next(owner_id, lease_seconds, now=current_time)
        return _job_from_row(row) if row is not None else None

    def _expire_terminal_leases(self, now: float) -> None:
        message = "Workflow 租约过期且已达到最大重试次数"
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            rows = connection.execute(
                """
                SELECT id, kind, attempts FROM workflow_jobs
                WHERE status = 'running' AND lease_until IS NOT NULL
                  AND lease_until <= ? AND attempts >= max_attempts
                ORDER BY created_at, id
                """,
                (now,),
            ).fetchall()
            for row in rows:
                sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM workflow_job_events
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (row["id"], int(row["attempts"])),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO workflow_job_events(
                        job_id, attempt, sequence, event_type, payload_json, created_at
                    ) VALUES (?, ?, ?, 'error', ?, ?)
                    """,
                    (
                        row["id"],
                        int(row["attempts"]),
                        sequence,
                        json.dumps(
                            _terminal_error_payload(str(row["kind"]), message),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        now,
                    ),
                )
                connection.execute(
                    """
                    UPDATE workflow_jobs
                    SET status = 'failed', last_error = ?, completed_at = ?, updated_at = ?,
                        lease_owner = NULL, lease_until = NULL
                    WHERE id = ? AND status = 'running' AND lease_until <= ?
                      AND attempts >= max_attempts
                    """,
                    (message, now, now, row["id"], now),
                )

    def _claim_next_fair(
        self,
        owner_id: str,
        *,
        lease_seconds: float,
        max_running_per_user: int,
        now: float,
    ) -> sqlite3.Row | None:
        running_limit = max(1, max_running_per_user)
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            row = connection.execute(
                """
                SELECT candidate.id
                FROM workflow_jobs AS candidate
                WHERE candidate.attempts < candidate.max_attempts
                  AND (
                      (candidate.status = 'pending' AND candidate.available_at <= ?)
                      OR (candidate.status = 'running' AND candidate.lease_until <= ?)
                  )
                  AND (
                      SELECT COUNT(*)
                      FROM workflow_jobs AS active
                      WHERE active.user_id = candidate.user_id
                        AND active.status = 'running'
                        AND active.lease_until > ?
                  ) < ?
                ORDER BY candidate.created_at, candidate.id
                LIMIT 1
                """,
                (now, now, now, running_limit),
            ).fetchone()
            if row is None:
                return None
            cursor = connection.execute(
                """
                UPDATE workflow_jobs
                SET status = 'running', attempts = attempts + 1,
                    lease_owner = ?, lease_until = ?, updated_at = ?
                WHERE id = ? AND attempts < max_attempts
                  AND (
                      (status = 'pending' AND available_at <= ?)
                      OR (status = 'running' AND lease_until <= ?)
                  )
                """,
                (
                    owner_id,
                    now + max(1.0, lease_seconds),
                    now,
                    row["id"],
                    now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                return None
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT * FROM workflow_jobs WHERE id = ?",
                    (row["id"],),
                ).fetchone(),
            )

    def owns_running_job(
        self,
        job_id: str,
        owner_id: str,
        *,
        now: float | None = None,
    ) -> bool:
        current_time = time.time() if now is None else now
        row = self._connection_provider().execute(
            """
            SELECT 1 FROM workflow_jobs
            WHERE id = ? AND status = 'running' AND lease_owner = ?
              AND lease_until > ?
            """,
            (job_id, owner_id, current_time),
        ).fetchone()
        return row is not None

    def renew_lease(
        self,
        job_id: str,
        owner_id: str,
        *,
        lease_seconds: float,
        now: float | None = None,
    ) -> bool:
        current_time = time.time() if now is None else now
        return cast(bool, self._state.renew_lease(job_id, owner_id, lease_seconds, now=current_time))

    def append_event(
        self,
        job_id: str,
        owner_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        now: float | None = None,
    ) -> WorkflowEvent:
        current_time = time.time() if now is None else now
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            job = connection.execute(
                """
                SELECT attempts FROM workflow_jobs
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                  AND lease_until > ?
                """,
                (job_id, owner_id, current_time),
            ).fetchone()
            if job is None:
                raise WorkflowLeaseLostError(f"Workflow Job 租约已失效: {job_id}")
            attempt = int(job["attempts"])
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                FROM workflow_job_events
                WHERE job_id = ? AND attempt = ?
                """,
                (job_id, attempt),
            ).fetchone()
            sequence = int(row["next_sequence"])
            serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
            connection.execute(
                """
                INSERT INTO workflow_job_events(
                    job_id, attempt, sequence, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, attempt, sequence, event_type, serialized, current_time),
            )
        return WorkflowEvent(job_id, attempt, sequence, event_type, payload, current_time)

    def list_events(
        self,
        job_id: str,
        *,
        user_id: int,
        attempt: int,
        after_sequence: int,
    ) -> list[WorkflowEvent]:
        rows = self._connection_provider().execute(
            """
            SELECT event.*
            FROM workflow_job_events AS event
            JOIN workflow_jobs AS job ON job.id = event.job_id
            WHERE event.job_id = ? AND job.user_id = ?
              AND event.attempt = ? AND event.sequence > ?
            ORDER BY event.sequence
            """,
            (job_id, user_id, attempt, after_sequence),
        ).fetchall()
        return [
            WorkflowEvent(
                job_id=str(row["job_id"]),
                attempt=int(row["attempt"]),
                sequence=int(row["sequence"]),
                event_type=str(row["event_type"]),
                payload=json.loads(row["payload_json"]),
                created_at=float(row["created_at"]),
            )
            for row in rows
        ]

    def complete(
        self,
        job_id: str,
        owner_id: str,
        *,
        completion_event: tuple[str, dict[str, Any]] | None = None,
        now: float | None = None,
    ) -> bool:
        current_time = time.time() if now is None else now
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            row = connection.execute(
                """
                SELECT attempts FROM workflow_jobs
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                  AND lease_until > ?
                """,
                (job_id, owner_id, current_time),
            ).fetchone()
            if row is None:
                return False
            if completion_event is not None:
                event_type, payload = completion_event
                sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM workflow_job_events
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (job_id, int(row["attempts"])),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO workflow_job_events(
                        job_id, attempt, sequence, event_type, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        int(row["attempts"]),
                        sequence,
                        event_type,
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
                        current_time,
                    ),
                )
            cursor = connection.execute(
                """
                UPDATE workflow_jobs
                SET status = 'succeeded', completed_at = ?, updated_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = NULL
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (current_time, current_time, job_id, owner_id),
            )
            return bool(cursor.rowcount == 1)

    def fail(
        self,
        job_id: str,
        owner_id: str,
        error: str,
        *,
        retry_delay_seconds: float,
        terminal_event: tuple[str, dict[str, Any]] | None = None,
        now: float | None = None,
    ) -> str | None:
        current_time = time.time() if now is None else now
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            row = connection.execute(
                """
                SELECT attempts, max_attempts FROM workflow_jobs
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (job_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            retrying = int(row["attempts"]) < int(row["max_attempts"])
            status = "pending" if retrying else "failed"
            if not retrying and terminal_event is not None:
                event_type, payload = terminal_event
                next_sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM workflow_job_events
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (job_id, int(row["attempts"])),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO workflow_job_events(
                        job_id, attempt, sequence, event_type, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        int(row["attempts"]),
                        next_sequence,
                        event_type,
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
                        current_time,
                    ),
                )
            cursor = connection.execute(
                """
                UPDATE workflow_jobs
                SET status = ?, available_at = ?, last_error = ?, updated_at = ?,
                    completed_at = ?, lease_owner = NULL, lease_until = NULL
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (
                    status,
                    current_time + max(0.0, retry_delay_seconds),
                    error[:1000],
                    current_time,
                    None if retrying else current_time,
                    job_id,
                    owner_id,
                ),
            )
            return cast(str | None, status if cursor.rowcount == 1 else None)

    def release(
        self,
        job_id: str,
        owner_id: str,
        reason: str,
        *,
        now: float | None = None,
    ) -> bool:
        current_time = time.time() if now is None else now
        return cast(bool, self._state.release(job_id, owner_id, reason, now=current_time))

    def cancel_owned(
        self,
        job_id: str,
        owner_id: str,
        *,
        event_payload: dict[str, Any],
        event_type: str = "error",
        reason: str = "服务关闭，任务已取消",
        now: float | None = None,
    ) -> bool:
        current_time = time.time() if now is None else now
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            row = connection.execute(
                """
                SELECT attempts FROM workflow_jobs
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (job_id, owner_id),
            ).fetchone()
            if row is None:
                return False
            sequence = int(
                connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) + 1
                    FROM workflow_job_events
                    WHERE job_id = ? AND attempt = ?
                    """,
                    (job_id, int(row["attempts"])),
                ).fetchone()[0]
            )
            cursor = connection.execute(
                """
                UPDATE workflow_jobs
                SET status = 'cancelled', completed_at = ?, updated_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = ?
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (current_time, current_time, reason[:1000], job_id, owner_id),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                """
                INSERT INTO workflow_job_events(
                    job_id, attempt, sequence, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    int(row["attempts"]),
                    sequence,
                    event_type,
                    json.dumps(event_payload, ensure_ascii=False, separators=(",", ":"), default=str),
                    current_time,
                ),
            )
            return True

    def cancel(
        self,
        job_id: str,
        *,
        user_id: int,
        event_payload: dict[str, Any],
        event_type: str = "error",
        now: float | None = None,
    ) -> WorkflowJob | None:
        current_time = time.time() if now is None else now
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            connection = work.connection
            row = connection.execute(
                "SELECT * FROM workflow_jobs WHERE id = ? AND user_id = ?",
                (job_id, user_id),
            ).fetchone()
            if row is None:
                return None
            if row["status"] in {"pending", "running"}:
                attempt = int(row["attempts"])
                sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM workflow_job_events
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (job_id, attempt),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    UPDATE workflow_jobs
                    SET status = 'cancelled', completed_at = ?, updated_at = ?,
                        lease_owner = NULL, lease_until = NULL, last_error = 'Cancelled'
                    WHERE id = ? AND user_id = ? AND status IN ('pending', 'running')
                    """,
                    (current_time, current_time, job_id, user_id),
                )
                connection.execute(
                    """
                    INSERT INTO workflow_job_events(
                        job_id, attempt, sequence, event_type, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        attempt,
                        sequence,
                        event_type,
                        json.dumps(event_payload, ensure_ascii=False, separators=(",", ":"), default=str),
                        current_time,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM workflow_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
            return _job_from_row(row)

    def purge_completed(self, retention_seconds: float, *, now: float | None = None) -> int:
        current_time = time.time() if now is None else now
        return cast(int, self._state.purge_completed(retention_seconds, now=current_time))

    def purge_completed_with_status(
        self,
        retention_seconds: float,
        *,
        now: float | None = None,
    ) -> PurgeResult:
        current_time = time.time() if now is None else now
        return self._state.purge_completed_with_status(retention_seconds, now=current_time)

    def queue_snapshot(self, *, now: float | None = None) -> dict[str, Any]:
        current_time = time.time() if now is None else now
        rows = self._connection_provider().execute(
            """
            SELECT status, COUNT(*) AS count, MIN(created_at) AS oldest_created_at,
                   MIN(CASE WHEN status = 'running' THEN lease_until END) AS oldest_lease_until
            FROM workflow_jobs
            WHERE status IN ('pending', 'running')
            GROUP BY status
            """
        ).fetchall()
        counts = {"pending": 0, "running": 0}
        oldest_created_at = None
        oldest_lease_until = None
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
            created_at = row["oldest_created_at"]
            lease_until = row["oldest_lease_until"]
            if created_at is not None:
                oldest_created_at = created_at if oldest_created_at is None else min(oldest_created_at, created_at)
            if lease_until is not None:
                oldest_lease_until = lease_until if oldest_lease_until is None else min(oldest_lease_until, lease_until)
        return {
            **counts,
            "oldest_age_seconds": max(0.0, current_time - oldest_created_at) if oldest_created_at else 0.0,
            "oldest_lease_age_seconds": max(0.0, current_time - oldest_lease_until) if oldest_lease_until else 0.0,
        }


workflow_job_store = WorkflowJobStore()


__all__ = [
    "WORKFLOW_JOB_SCHEMA",
    "WORKFLOW_JOB_STATEMENTS",
    "WORKFLOW_ACTIVE_USER_INDEX",
    "WorkflowEvent",
    "WorkflowJob",
    "WorkflowJobStore",
    "WorkflowKind",
    "WorkflowLeaseLostError",
    "WorkflowQueueFullError",
    "WorkflowRequestMismatchError",
    "WorkflowSubmission",
    "workflow_job_store",
]
