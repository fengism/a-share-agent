"""Portfolio SQLite 持久化实现。"""

from collections.abc import Callable
from typing import Any

from app.infrastructure.persistence.connection import get_connection as get_db_connection
from app.infrastructure.persistence.connection import unit_of_work

PortfolioValidator = Callable[[list[dict[str, Any]]], object]


def get_connection():
    """获取用户核心数据库连接。"""
    return get_db_connection("user")


def _list_transactions(
    connection,
    user_id: int,
    stock_code: str | None = None,
) -> list[dict[str, Any]]:
    if stock_code is None:
        rows = connection.execute(
            """
            SELECT id, user_id, stock_code, stock_name, side, trade_price,
                   trade_time, shares, fee, note, created_at
            FROM portfolio_transactions
            WHERE user_id = ?
            ORDER BY trade_time, id
            """,
            (user_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT id, user_id, stock_code, stock_name, side, trade_price,
                   trade_time, shares, fee, note, created_at
            FROM portfolio_transactions
            WHERE user_id = ? AND stock_code = ?
            ORDER BY trade_time, id
            """,
            (user_id, stock_code),
        ).fetchall()
    return [dict(row) for row in rows]


def list_transactions(
    user_id: int,
    *,
    stock_code: str | None = None,
    connection=None,
) -> list[dict[str, Any]]:
    return _list_transactions(connection or get_connection(), user_id, stock_code)


def get_transaction(user_id: int, transaction_id: int, *, connection=None) -> dict[str, Any] | None:
    row = (
        (connection or get_connection())
        .execute(
            "SELECT * FROM portfolio_transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        )
        .fetchone()
    )
    return dict(row) if row is not None else None


def get_latest_stock_name(user_id: int, stock_code: str, *, connection=None) -> str:
    row = (
        (connection or get_connection())
        .execute(
            """
            SELECT stock_name
            FROM portfolio_transactions
            WHERE user_id = ? AND stock_code = ? AND stock_name <> ''
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, stock_code),
        )
        .fetchone()
    )
    return str(row["stock_name"]) if row is not None else ""


def create_transaction(
    user_id: int,
    stock_code: str,
    stock_name: str,
    side: str,
    trade_price: float,
    trade_time: str,
    shares: int,
    fee: float,
    note: str,
    *,
    validator: PortfolioValidator,
    connection=None,
) -> dict[str, Any]:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        cursor = work.connection.execute(
            """
            INSERT INTO portfolio_transactions(
                user_id, stock_code, stock_name, side, trade_price,
                trade_time, shares, fee, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                stock_code,
                stock_name,
                side,
                trade_price,
                trade_time,
                shares,
                fee,
                note,
            ),
        )
        validator(_list_transactions(work.connection, user_id, stock_code))
        row = work.connection.execute(
            "SELECT * FROM portfolio_transactions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def update_transaction(
    user_id: int,
    transaction_id: int,
    stock_code: str,
    stock_name: str,
    side: str,
    trade_price: float,
    trade_time: str,
    shares: int,
    fee: float,
    note: str,
    *,
    validator: PortfolioValidator,
    connection=None,
) -> dict[str, Any] | None:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        existing = work.connection.execute(
            "SELECT stock_code FROM portfolio_transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        ).fetchone()
        if existing is None:
            return None
        previous_stock_code = str(existing["stock_code"])
        work.connection.execute(
            """
            UPDATE portfolio_transactions
            SET stock_code = ?, stock_name = ?, side = ?, trade_price = ?,
                trade_time = ?, shares = ?, fee = ?, note = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                stock_code,
                stock_name,
                side,
                trade_price,
                trade_time,
                shares,
                fee,
                note,
                transaction_id,
                user_id,
            ),
        )
        if previous_stock_code != stock_code:
            validator(_list_transactions(work.connection, user_id, previous_stock_code))
        validator(_list_transactions(work.connection, user_id, stock_code))
        row = work.connection.execute(
            "SELECT * FROM portfolio_transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        ).fetchone()
    return dict(row)


def delete_transaction(
    user_id: int,
    transaction_id: int,
    *,
    validator: PortfolioValidator,
    connection=None,
) -> bool:
    target = connection or get_connection()
    with unit_of_work(connection=target, immediate=True) as work:
        transaction = work.connection.execute(
            "SELECT stock_code FROM portfolio_transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        ).fetchone()
        if transaction is None:
            return False
        work.connection.execute(
            "DELETE FROM portfolio_transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        )
        validator(_list_transactions(work.connection, user_id, str(transaction["stock_code"])))
    return True
