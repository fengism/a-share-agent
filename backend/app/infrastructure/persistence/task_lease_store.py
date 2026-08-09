import time

from app.infrastructure.persistence.connection import get_connection


def acquire_task_lease(
    task_name: str,
    owner_id: str,
    lease_seconds: float,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    lease_until = current_time + max(0.0, lease_seconds)
    conn = get_connection()
    cursor = conn.execute(
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
    conn.commit()
    return cursor.rowcount == 1


def renew_task_lease(
    task_name: str,
    owner_id: str,
    lease_seconds: float,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE background_task_leases
        SET lease_until = ?, updated_at = ?
        WHERE task_name = ? AND owner_id = ?
        """,
        (current_time + max(0.0, lease_seconds), current_time, task_name, owner_id),
    )
    conn.commit()
    return cursor.rowcount == 1


def release_task_lease(task_name: str, owner_id: str) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM background_task_leases WHERE task_name = ? AND owner_id = ?",
        (task_name, owner_id),
    )
    conn.commit()
    return cursor.rowcount == 1


def purge_expired_task_leases(*, now: float | None = None) -> int:
    current_time = time.time() if now is None else now
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM background_task_leases WHERE lease_until <= ?",
        (current_time,),
    )
    conn.commit()
    return cursor.rowcount
