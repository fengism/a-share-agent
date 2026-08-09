"""Bot Command 持久化任务仓储。"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.infrastructure.persistence.leased_jobs import LeasedJobSpec, LeasedJobStateStore

JOB_STATUSES = frozenset({"pending", "running", "succeeded", "failed"})

_JOB_STATE = LeasedJobStateStore(
    LeasedJobSpec(table_name="bot_command_jobs"),
    lambda: get_connection("user"),
)


@dataclass(frozen=True, slots=True)
class BotJob:
    id: str
    event_id: str
    platform: str
    request_user_id: str
    command_name: str
    message_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: float
    updated_at: float
    completed_at: float | None


def _delete_completed(conn: sqlite3.Connection, cutoff: float) -> int:
    return conn.execute(
        """
        DELETE FROM bot_command_jobs
        WHERE status IN ('succeeded', 'failed')
          AND completed_at IS NOT NULL
          AND completed_at <= ?
        """,
        (cutoff,),
    ).rowcount


def enqueue(
    *,
    event_id: str,
    platform: str,
    message_payload: dict[str, Any],
    max_attempts: int,
    dedup_ttl_seconds: int,
    request_user_id: str = "",
    command_name: str = "",
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    with unit_of_work("user", immediate=True) as work:
        conn = work.connection
        _delete_completed(conn, current_time - max(1, dedup_ttl_seconds))
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO bot_command_jobs(
                id, event_id, platform, request_user_id, command_name, message_json,
                status, attempts, max_attempts, available_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                event_id,
                platform,
                request_user_id,
                command_name,
                json.dumps(message_payload, ensure_ascii=False, separators=(",", ":")),
                max(1, max_attempts),
                current_time,
                current_time,
                current_time,
            ),
        )
        return cursor.rowcount == 1


def purge_completed(retention_seconds: int, *, now: float | None = None) -> int:
    current_time = time.time() if now is None else now
    return _JOB_STATE.purge_completed(max(1, retention_seconds), now=current_time)


def claim_next(
    owner_id: str,
    lease_seconds: int,
    *,
    now: float | None = None,
) -> BotJob | None:
    current_time = time.time() if now is None else now
    claimed = _JOB_STATE.claim_next(
        owner_id,
        lease_seconds,
        now=current_time,
    )
    return _job_from_row(claimed) if claimed is not None else None


def renew_lease(
    job_id: str,
    owner_id: str,
    lease_seconds: int,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    return _JOB_STATE.renew_lease(
        job_id,
        owner_id,
        lease_seconds,
        now=current_time,
    )


def save_response(
    job_id: str,
    owner_id: str,
    response_payload: dict[str, Any],
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    conn = get_connection("user")
    cursor = conn.execute(
        """
        UPDATE bot_command_jobs
        SET response_json = ?, updated_at = ?
        WHERE id = ? AND status = 'running' AND lease_owner = ?
        """,
        (
            json.dumps(response_payload, ensure_ascii=False, separators=(",", ":")),
            current_time,
            job_id,
            owner_id,
        ),
    )
    conn.commit()
    return cursor.rowcount == 1


def complete(
    job_id: str,
    owner_id: str,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    return _JOB_STATE.complete(job_id, owner_id, now=current_time)


def release(
    job_id: str,
    owner_id: str,
    reason: str,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    return _JOB_STATE.release(job_id, owner_id, reason, now=current_time)


def fail(
    job_id: str,
    owner_id: str,
    error: str,
    retry_delay_seconds: float,
    *,
    now: float | None = None,
) -> str | None:
    current_time = time.time() if now is None else now
    return _JOB_STATE.fail(
        job_id,
        owner_id,
        error,
        retry_delay_seconds,
        now=current_time,
    )


def get_job(job_id: str) -> BotJob | None:
    row = get_connection("user").execute(
        "SELECT * FROM bot_command_jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    return _job_from_row(row) if row is not None else None


def get_job_by_event_id(event_id: str) -> BotJob | None:
    row = get_connection("user").execute(
        "SELECT * FROM bot_command_jobs WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    return _job_from_row(row) if row is not None else None


def list_recent_jobs(request_user_id: str, *, limit: int = 5) -> list[BotJob]:
    rows = get_connection("user").execute(
        """
        SELECT *
        FROM bot_command_jobs
        WHERE request_user_id = ? AND command_name != 'task'
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (request_user_id, max(1, min(limit, 20))),
    ).fetchall()
    return [_job_from_row(row) for row in rows]


def find_jobs_by_id_prefix(request_user_id: str, job_id_prefix: str) -> list[BotJob]:
    rows = get_connection("user").execute(
        """
        SELECT *
        FROM bot_command_jobs
        WHERE request_user_id = ?
          AND command_name != 'task'
          AND id LIKE ?
        ORDER BY created_at DESC, id DESC
        LIMIT 2
        """,
        (request_user_id, f"{job_id_prefix}%"),
    ).fetchall()
    return [_job_from_row(row) for row in rows]


def list_jobs(*, status: str | None = None, limit: int = 50) -> list[BotJob]:
    if status is not None and status not in JOB_STATUSES:
        raise ValueError(f"未知 Bot 任务状态: {status}")
    conn = get_connection("user")
    if status is None:
        rows = conn.execute(
            "SELECT * FROM bot_command_jobs ORDER BY created_at DESC, id DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM bot_command_jobs
            WHERE status = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (status, max(1, min(limit, 200))),
        ).fetchall()
    return [_job_from_row(row) for row in rows]


def count_jobs_by_status() -> dict[str, int]:
    counts = {status: 0 for status in JOB_STATUSES}
    rows = get_connection("user").execute(
        "SELECT status, COUNT(*) AS count FROM bot_command_jobs GROUP BY status"
    ).fetchall()
    for row in rows:
        counts[str(row["status"])] = int(row["count"])
    return counts


def retry_failed(job_id: str, *, now: float | None = None) -> bool:
    current_time = time.time() if now is None else now
    return _JOB_STATE.retry_failed(job_id, now=current_time)


def get_status(job_id: str) -> str | None:
    row = get_connection("user").execute(
        "SELECT status FROM bot_command_jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    return str(row["status"]) if row is not None else None


def _job_from_row(row: sqlite3.Row) -> BotJob:
    response_json = row["response_json"]
    return BotJob(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        platform=str(row["platform"]),
        request_user_id=str(row["request_user_id"]),
        command_name=str(row["command_name"]),
        message_payload=json.loads(row["message_json"]),
        response_payload=json.loads(response_json) if response_json else None,
        status=str(row["status"]),
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        last_error=str(row["last_error"]) if row["last_error"] else None,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        completed_at=float(row["completed_at"]) if row["completed_at"] is not None else None,
    )
