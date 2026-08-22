"""量化回测持久化任务仓储。"""

import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.infrastructure.persistence.leased_jobs import LeasedJobSpec, LeasedJobStateStore
from app.infrastructure.persistence.retention import PurgeResult

QUANT_RUN_RETENTION_SECONDS = 90 * 24 * 60 * 60

_RUN_STATE = LeasedJobStateStore(
    LeasedJobSpec(
        table_name="quant_backtest_runs",
        terminal_statuses=("succeeded", "failed", "cancelled"),
    ),
    lambda: get_connection("user"),
)


class ActiveRunLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuantRunRow:
    id: str
    user_id: int
    name: str
    request: dict[str, Any]
    result: dict[str, Any] | None
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: float
    updated_at: float
    completed_at: float | None
    lease_owner: str | None = None
    input_snapshot: dict[str, Any] | None = None


def _loads(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None


def _row_to_run(row) -> QuantRunRow:
    return QuantRunRow(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        request=_loads(row["request_json"]) or {},
        result=_loads(row["result_json"]),
        status=row["status"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        lease_owner=row["lease_owner"],
        input_snapshot=_loads(row["input_snapshot_json"]),
    )


def create_run(
    user_id: int,
    name: str,
    request: dict[str, Any],
    *,
    max_active_runs: int | None = None,
    now: float | None = None,
) -> QuantRunRow:
    current_time = time.time() if now is None else now
    run_id = uuid4().hex
    with unit_of_work("user", immediate=True) as work:
        connection = work.connection
        if max_active_runs is not None:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count FROM quant_backtest_runs
                WHERE user_id = ? AND status IN ('pending', 'running')
                """,
                (user_id,),
            ).fetchone()
            if int(row["count"]) >= max_active_runs:
                raise ActiveRunLimitError(f"每个用户最多同时运行 {max_active_runs} 个回测任务")
        connection.execute(
            """
            INSERT INTO quant_backtest_runs(
                id, user_id, name, request_json, status, attempts, max_attempts,
                available_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'pending', 0, 2, ?, ?, ?)
            """,
            (
                run_id,
                user_id,
                name,
                json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                current_time,
                current_time,
                current_time,
            ),
        )
    return get_run(user_id, run_id)


def get_run(user_id: int, run_id: str) -> QuantRunRow | None:
    row = get_connection("user").execute(
        "SELECT * FROM quant_backtest_runs WHERE id = ? AND user_id = ?",
        (run_id, user_id),
    ).fetchone()
    return _row_to_run(row) if row is not None else None


def list_runs(user_id: int, *, limit: int = 50, offset: int = 0) -> list[QuantRunRow]:
    rows = get_connection("user").execute(
        """
        SELECT * FROM quant_backtest_runs
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    ).fetchall()
    return [_row_to_run(row) for row in rows]


def count_active_runs(user_id: int) -> int:
    row = get_connection("user").execute(
        """
        SELECT COUNT(*) AS count
        FROM quant_backtest_runs
        WHERE user_id = ? AND status IN ('pending', 'running')
        """,
        (user_id,),
    ).fetchone()
    return int(row["count"])


def claim_next(owner_id: str, *, lease_seconds: int = 600, now: float | None = None) -> QuantRunRow | None:
    current_time = time.time() if now is None else now
    claimed = _RUN_STATE.claim_next(
        owner_id,
        lease_seconds,
        now=current_time,
    )
    return _row_to_run(claimed) if claimed is not None else None


def renew_lease(
    run_id: str,
    owner_id: str,
    lease_seconds: float,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    return _RUN_STATE.renew_lease(
        run_id,
        owner_id,
        lease_seconds,
        now=current_time,
    )


def release(
    run_id: str,
    owner_id: str,
    reason: str,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    return _RUN_STATE.release(run_id, owner_id, reason, now=current_time)


def complete(
    run_id: str,
    owner_id: str,
    result: dict[str, Any],
    input_snapshot: dict[str, Any],
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    return _RUN_STATE.complete(
        run_id,
        owner_id,
        now=current_time,
        updates={
            "result_json": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            "input_snapshot_json": json.dumps(input_snapshot, ensure_ascii=False, separators=(",", ":")),
            "data_hash": result.get("data_hash"),
            "engine_version": result.get("engine_version"),
        },
    )


def fail(
    run_id: str,
    owner_id: str,
    error: str,
    *,
    retry_delay_seconds: float = 2,
    now: float | None = None,
) -> str | None:
    current_time = time.time() if now is None else now
    return _RUN_STATE.fail(
        run_id,
        owner_id,
        error,
        retry_delay_seconds,
        now=current_time,
    )


def cancel(user_id: int, run_id: str, *, now: float | None = None) -> bool:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_backtest_runs
        SET status = 'cancelled', lease_owner = NULL, lease_until = NULL,
            updated_at = ?, completed_at = ?
        WHERE id = ? AND user_id = ? AND status IN ('pending', 'running')
        """,
        (current_time, current_time, run_id, user_id),
    )
    connection.commit()
    return cursor.rowcount == 1


def retry_failed(user_id: int, run_id: str, *, now: float | None = None) -> bool:
    current_time = time.time() if now is None else now
    return _RUN_STATE.retry_failed(
        run_id,
        now=current_time,
        filters={"user_id": user_id},
    )


def delete_run(user_id: int, run_id: str) -> bool:
    connection = get_connection("user")
    cursor = connection.execute(
        """
        DELETE FROM quant_backtest_runs
        WHERE id = ? AND user_id = ? AND status NOT IN ('pending', 'running')
        """,
        (run_id, user_id),
    )
    connection.commit()
    return cursor.rowcount == 1


def purge_completed(*, retention_seconds: int = QUANT_RUN_RETENTION_SECONDS, now: float | None = None) -> int:
    current_time = time.time() if now is None else now
    return _RUN_STATE.purge_completed(retention_seconds, now=current_time)


def purge_completed_with_status(
    *,
    retention_seconds: int = QUANT_RUN_RETENTION_SECONDS,
    now: float | None = None,
) -> PurgeResult:
    current_time = time.time() if now is None else now
    return _RUN_STATE.purge_completed_with_status(retention_seconds, now=current_time)
