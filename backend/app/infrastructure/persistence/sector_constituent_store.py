"""开盘红板块成分股快照的 SQLite 持久化。"""

from __future__ import annotations

import json
from collections.abc import Iterable

from app.core.market import normalize_code
from app.infrastructure.persistence.connection import get_connection, unit_of_work


def _normalize_stocks(stocks: Iterable[dict]) -> list[dict]:
    """标准化并按首次出现顺序去重；非法股票代码不落库。"""
    normalized: list[dict] = []
    seen: set[str] = set()
    for stock in stocks:
        try:
            code = normalize_code(str(stock.get("code") or "")).raw
        except ValueError:
            continue
        if code in seen:
            continue
        seen.add(code)
        item = dict(stock)
        item["code"] = code
        normalized.append(item)
    return normalized


def replace_snapshot(
    *,
    source: str,
    plate_id: str,
    constituent_date: str,
    fetched_at: str,
    stocks: list[dict],
) -> None:
    """原子替换指定板块、日期的完整成分股快照。"""
    normalized = _normalize_stocks(stocks)
    with unit_of_work("market", immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO sector_constituent_snapshots(
                source, plate_id, constituent_date, fetched_at, stock_count
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, plate_id, constituent_date) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                stock_count = excluded.stock_count
            """,
            (source, plate_id, constituent_date, fetched_at, len(normalized)),
        )
        work.connection.execute(
            """
            DELETE FROM sector_constituents
            WHERE source = ? AND plate_id = ? AND constituent_date = ?
            """,
            (source, plate_id, constituent_date),
        )
        work.connection.executemany(
            """
            INSERT INTO sector_constituents(
                source, plate_id, constituent_date, stock_code,
                stock_name, tags, position, history_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    source,
                    plate_id,
                    constituent_date,
                    stock["code"],
                    str(stock.get("name") or ""),
                    str(stock.get("tags") or ""),
                    position,
                    json.dumps(stock, ensure_ascii=False, separators=(",", ":")),
                )
                for position, stock in enumerate(normalized)
            ],
        )


def _load_snapshot_where(where_clause: str, params: tuple[str, ...]) -> dict | None:
    connection = get_connection("market")
    metadata = connection.execute(
        f"""
        SELECT source, plate_id, constituent_date, fetched_at, stock_count
        FROM sector_constituent_snapshots
        WHERE {where_clause}
        ORDER BY constituent_date DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if metadata is None:
        return None

    rows = connection.execute(
        """
        SELECT history_json
        FROM sector_constituents
        WHERE source = ? AND plate_id = ? AND constituent_date = ?
        ORDER BY position ASC
        """,
        (metadata["source"], metadata["plate_id"], metadata["constituent_date"]),
    ).fetchall()
    stocks: list[dict] = []
    for row in rows:
        try:
            stock = json.loads(row["history_json"])
        except (TypeError, ValueError):
            continue
        if isinstance(stock, dict):
            stocks.append(stock)
    return {
        "source": metadata["source"],
        "plate_id": metadata["plate_id"],
        "constituent_date": metadata["constituent_date"],
        "fetched_at": metadata["fetched_at"],
        "stock_count": int(metadata["stock_count"]),
        "stocks": stocks,
    }


def load_snapshot(source: str, plate_id: str, constituent_date: str) -> dict | None:
    """读取指定日期的板块成分股快照，包括已缓存的空快照。"""
    return _load_snapshot_where(
        "source = ? AND plate_id = ? AND constituent_date = ?",
        (source, plate_id, constituent_date),
    )


def load_latest_snapshot_before(
    source: str,
    plate_id: str,
    before_date: str,
) -> dict | None:
    """读取不晚于指定日期的最新板块成分股快照。"""
    return _load_snapshot_where(
        "source = ? AND plate_id = ? AND constituent_date <= ?",
        (source, plate_id, before_date),
    )
