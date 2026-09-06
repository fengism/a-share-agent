"""用户自选股与提醒规则持久化。"""

from typing import Any

from app.infrastructure.persistence.connection import get_connection as get_db_connection
from app.infrastructure.persistence.connection import unit_of_work


def get_connection():
    return get_db_connection("user")


def list_items(user_id: int, *, connection=None) -> list[dict[str, Any]]:
    rows = (connection or get_connection()).execute(
        """
        SELECT id, user_id, stock_code, stock_name, note, created_at
        FROM watchlist_items
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_item(user_id: int, stock_code: str, *, connection=None) -> dict[str, Any] | None:
    row = (connection or get_connection()).execute(
        "SELECT * FROM watchlist_items WHERE user_id = ? AND stock_code = ?",
        (user_id, stock_code),
    ).fetchone()
    return dict(row) if row is not None else None


def add_item(
    user_id: int,
    stock_code: str,
    stock_name: str,
    note: str,
    *,
    connection=None,
) -> dict[str, Any]:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO watchlist_items(user_id, stock_code, stock_name, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, stock_code) DO UPDATE SET
                stock_name = excluded.stock_name,
                note = excluded.note
            """,
            (user_id, stock_code, stock_name, note),
        )
        row = work.connection.execute(
            "SELECT * FROM watchlist_items WHERE user_id = ? AND stock_code = ?",
            (user_id, stock_code),
        ).fetchone()
    return dict(row)


def delete_item(user_id: int, stock_code: str, *, connection=None) -> bool:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        result = work.connection.execute(
            "DELETE FROM watchlist_items WHERE user_id = ? AND stock_code = ?",
            (user_id, stock_code),
        )
    return result.rowcount == 1


ALERTS_MAX_PER_USER = 200


def list_alerts(user_id: int, stock_code: str | None = None, *, connection=None) -> list[dict[str, Any]]:
    target = connection or get_connection()
    if stock_code is None:
        rows = target.execute(
            "SELECT * FROM watchlist_alerts WHERE user_id = ? ORDER BY id LIMIT ?",
            (user_id, ALERTS_MAX_PER_USER),
        ).fetchall()
    else:
        rows = target.execute(
            "SELECT * FROM watchlist_alerts WHERE user_id = ? AND stock_code = ? ORDER BY id LIMIT ?",
            (user_id, stock_code, ALERTS_MAX_PER_USER),
        ).fetchall()
    return [dict(row) for row in rows]


def add_alert(
    user_id: int,
    stock_code: str,
    condition: str,
    threshold: float,
    *,
    connection=None,
) -> dict[str, Any]:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        existing = work.connection.execute(
            "SELECT COUNT(*) FROM watchlist_alerts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if existing >= ALERTS_MAX_PER_USER:
            raise ValueError(f"每个用户的告警数量上限为 {ALERTS_MAX_PER_USER}")
        cursor = work.connection.execute(
            """
            INSERT INTO watchlist_alerts(user_id, stock_code, condition, threshold)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, stock_code, condition, threshold),
        )
        row = work.connection.execute(
            "SELECT * FROM watchlist_alerts WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def delete_alert(user_id: int, alert_id: int, *, connection=None) -> bool:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        result = work.connection.execute(
            "DELETE FROM watchlist_alerts WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
    return result.rowcount == 1
