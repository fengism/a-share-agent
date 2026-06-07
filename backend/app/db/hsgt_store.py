import logging

from app.db.connection import get_connection

logger = logging.getLogger(__name__)


def save_hsgt_flow(date: str, points: list[dict], updated_at: str) -> None:
    """批量写入指定日期的北向资金分钟级数据。

    Param:
        date: 日期字符串，格式 YYYY-MM-DD。
        points: 分钟级数据点列表，每项包含 time、hgt、sgt、total 等字段。
        updated_at: 数据更新时间戳。
    Return:
        无。
    """
    conn = get_connection()
    rows = [
        (date, p["time"], p.get("hgt"), p.get("sgt"), p.get("total"), updated_at)
        for p in points
        if p.get("time")
    ]
    if not rows:
        return
    conn.executemany(
        "INSERT OR REPLACE INTO hsgt_flow (date, time, hgt, sgt, total, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    logger.debug(f"写入北向数据: date={date}, rows={len(rows)}")


def query_hsgt_flow(date: str) -> list[dict]:
    """查询指定日期的全部分钟级北向资金数据。

    Param:
        date: 日期字符串，格式 YYYY-MM-DD。
    Return:
        包含 time、hgt、sgt、total 字段的字典列表，按时间升序排列。
    """
    conn = get_connection()
    cursor = conn.execute(
        "SELECT time, hgt, sgt, total FROM hsgt_flow WHERE date = ? ORDER BY time",
        (date,),
    )
    return [dict(row) for row in cursor.fetchall()]


def query_hsgt_dates(limit: int = 30) -> list[dict]:
    """查询有北向资金数据的日期列表，每日返回最终净买入。

    Param:
        limit: 返回的最大日期数量。
    Return:
        包含 date、total、updated_at 字段的字典列表，按日期降序排列。
    """
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT date, MAX(total) AS total, MAX(updated_at) AS updated_at
        FROM hsgt_flow
        GROUP BY date
        ORDER BY date DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]
