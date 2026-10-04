import sqlite3
import time

from app.infrastructure.persistence.connection import get_connection, is_busy_error, unit_of_work
from app.infrastructure.persistence.retention import PurgeResult, purge_rows_in_batches


def acquire_task_lease(
    task_name: str,
    owner_id: str,
    lease_seconds: float,
    *,
    now: float | None = None,
    max_retries: int = 5,
    retry_backoff: float = 0.05,
) -> bool:
    current_time = time.time() if now is None else now
    lease_until = current_time + max(0.0, lease_seconds)
    for attempt in range(max_retries):
        try:
            conn = get_connection("market")
            if conn.in_transaction:
                conn.rollback()
            with unit_of_work("market", immediate=True) as uow:
                cursor = uow.connection.execute(
                    """
                    INSERT INTO background_task_leases(task_name, owner_id, lease_until, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(task_name) DO UPDATE SET
                        owner_id = excluded.owner_id,
                        lease_until = excluded.lease_until,
                        updated_at = excluded.updated_at
                    WHERE background_task_leases.owner_id = excluded.owner_id
                       OR background_task_leases.lease_until <= ?
                    """,
                    (task_name, owner_id, lease_until, current_time, current_time),
                )
                return cursor.rowcount == 1
        except sqlite3.OperationalError as exc:
            if is_busy_error(exc) and attempt < max_retries - 1:
                time.sleep(retry_backoff * (2**attempt))
                continue
            raise
    return False


def renew_task_lease(
    task_name: str,
    owner_id: str,
    lease_seconds: float,
    *,
    now: float | None = None,
    max_retries: int = 5,
    retry_backoff: float = 0.05,
) -> bool:
    current_time = time.time() if now is None else now
    for attempt in range(max_retries):
        try:
            conn = get_connection("market")
            if conn.in_transaction:
                conn.rollback()
            with unit_of_work("market", immediate=True) as uow:
                cursor = uow.connection.execute(
                    """
                    UPDATE background_task_leases
                    SET lease_until = ?, updated_at = ?
                    WHERE task_name = ? AND owner_id = ?
                    """,
                    (current_time + max(0.0, lease_seconds), current_time, task_name, owner_id),
                )
                return cursor.rowcount == 1
        except sqlite3.OperationalError as exc:
            if is_busy_error(exc) and attempt < max_retries - 1:
                time.sleep(retry_backoff * (2**attempt))
                continue
            raise
    return False


def release_task_lease(
    task_name: str,
    owner_id: str,
    *,
    max_retries: int = 5,
    retry_backoff: float = 0.05,
) -> bool:
    for attempt in range(max_retries):
        try:
            conn = get_connection("market")
            if conn.in_transaction:
                conn.rollback()
            with unit_of_work("market", immediate=True) as uow:
                cursor = uow.connection.execute(
                    "DELETE FROM background_task_leases WHERE task_name = ? AND owner_id = ?",
                    (task_name, owner_id),
                )
                return cursor.rowcount == 1
        except sqlite3.OperationalError as exc:
            if is_busy_error(exc) and attempt < max_retries - 1:
                time.sleep(retry_backoff * (2**attempt))
                continue
            raise
    return False


def purge_expired_task_leases(*, now: float | None = None) -> int:
    return purge_expired_task_leases_with_status(now=now).deleted


def purge_expired_task_leases_with_status(*, now: float | None = None) -> PurgeResult:
    current_time = time.time() if now is None else now
    conn = get_connection("market")
    if conn.in_transaction:
        conn.rollback()
    return purge_rows_in_batches(
        conn,
        table_name="background_task_leases",
        predicate_sql="lease_until <= ?",
        parameters=(current_time,),
        order_by="lease_until, rowid",
    )

