"""Portfolio SQLite 持久化实现。"""

from app.infrastructure.persistence.connection import get_connection as get_db_connection


def get_connection():
    """获取用户核心数据库连接。"""
    return get_db_connection("user")


def create_position(
    user_id: int,
    stock_code: str,
    stock_name: str,
    buy_price: float,
    buy_time: str,
    shares: int,
) -> dict:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO portfolio_positions(user_id, stock_code, stock_name, buy_price, buy_time, shares)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, stock_code, stock_name, buy_price, buy_time, shares),
    )
    conn.commit()
    return get_position(user_id, cursor.lastrowid)


def get_position(user_id: int, position_id: int) -> dict:
    row = get_connection().execute(
        "SELECT * FROM portfolio_positions WHERE id = ? AND user_id = ?",
        (position_id, user_id),
    ).fetchone()
    if row is None:
        raise LookupError("持仓记录不存在")
    return dict(row)


def list_positions(user_id: int) -> list[dict]:
    rows = get_connection().execute(
        """
        SELECT id, stock_code, stock_name, buy_price, buy_time, shares
        FROM portfolio_positions
        WHERE user_id = ?
        ORDER BY buy_time DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_position(user_id: int, position_id: int) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM portfolio_positions WHERE id = ? AND user_id = ?",
        (position_id, user_id),
    )
    conn.commit()
    return cursor.rowcount > 0
