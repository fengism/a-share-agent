"""Bot 用户共享滑动窗口限流仓储。"""

import time

from app.infrastructure.persistence.connection import get_connection, unit_of_work


def _delete_expired(conn, cutoff: float) -> int:
    return conn.execute(
        "DELETE FROM bot_rate_limit_events WHERE occurred_at <= ?",
        (cutoff,),
    ).rowcount


def allow(
    scope_key: str,
    max_requests: int,
    window_seconds: int,
    *,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    request_limit = max(1, max_requests)
    window = max(1, window_seconds)
    window_start = current_time - window
    with unit_of_work("user", immediate=True) as work:
        conn = work.connection
        _delete_expired(conn, window_start)
        count = conn.execute(
            """
            SELECT COUNT(*) AS request_count
            FROM bot_rate_limit_events
            WHERE scope_key = ? AND occurred_at > ?
            """,
            (scope_key, window_start),
        ).fetchone()["request_count"]
        if count >= request_limit:
            return False
        conn.execute(
            "INSERT INTO bot_rate_limit_events(scope_key, occurred_at) VALUES (?, ?)",
            (scope_key, current_time),
        )
        return True


def purge_expired(window_seconds: int, *, now: float | None = None) -> int:
    current_time = time.time() if now is None else now
    conn = get_connection("user")
    deleted = _delete_expired(conn, current_time - max(1, window_seconds))
    conn.commit()
    return deleted
