"""分析历史索引存储。"""

import json
import logging
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from app.infrastructure.persistence.connection import get_connection
from app.infrastructure.persistence.history_index import HistoryIndexCoordinator

HistorySummary = dict[str, object]
HistoryFile = tuple[int, str, Path]
SummaryLoader = Callable[[Path, str], HistorySummary | None]
HistoryRowBuilder = Callable[[int, Path, HistorySummary], tuple[object, ...]]

_UPSERT_HISTORY_SQL = """
INSERT INTO analysis_history_index (
    storage_root, scope_user_id, stock_code, analysis_date, stock_name,
    current_price, overall_rating, signal, confidence, file_path
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(storage_root, scope_user_id, stock_code, analysis_date) DO UPDATE SET
    stock_name = excluded.stock_name,
    current_price = excluded.current_price,
    overall_rating = excluded.overall_rating,
    signal = excluded.signal,
    confidence = excluded.confidence,
    file_path = excluded.file_path
"""


def summary_from_path(
    filepath: Path,
    fallback_code: str,
    logger: logging.Logger,
) -> HistorySummary | None:
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("跳过失效的分析文件: %s, error=%s", filepath, exc)
        return None
    return {
        "stock_code": data.get("stock_code", fallback_code),
        "stock_name": data.get("stock_name", ""),
        "analysis_date": data.get("analysis_date", filepath.stem),
        "current_price": data.get("current_price"),
        "overall_rating": data.get("overall_rating"),
        "signal": data.get("signal"),
        "confidence": data.get("confidence"),
    }


def history_row(
    coordinator: HistoryIndexCoordinator,
    scope_user_id: int,
    filepath: Path,
    summary: HistorySummary,
) -> tuple[object, ...]:
    return (
        coordinator.storage_root(),
        scope_user_id,
        summary.get("stock_code", filepath.parent.name),
        summary.get("analysis_date", filepath.stem),
        summary.get("stock_name", ""),
        summary.get("current_price"),
        summary.get("overall_rating"),
        summary.get("signal"),
        summary.get("confidence"),
        str(filepath),
    )


def upsert_history_row(
    coordinator: HistoryIndexCoordinator,
    row: tuple[object, ...],
) -> None:
    coordinator.write(lambda connection: connection.execute(_UPSERT_HISTORY_SQL, row))


def delete_history_row(
    coordinator: HistoryIndexCoordinator,
    scope_user_id: int,
    code: str,
    date: str,
) -> None:
    coordinator.write(
        lambda connection: connection.execute(
            """
            DELETE FROM analysis_history_index
            WHERE storage_root = ? AND scope_user_id = ?
              AND stock_code = ? AND analysis_date = ?
            """,
            (coordinator.storage_root(), scope_user_id, code, date),
        )
    )


def iter_history_files(data_dir: Path, users_dir_name: str) -> Iterator[HistoryFile]:
    if not data_dir.exists():
        return
    for stock_dir in data_dir.iterdir():
        if not stock_dir.is_dir() or stock_dir.name == users_dir_name:
            continue
        for filepath in stock_dir.glob("*.json"):
            yield 0, stock_dir.name, filepath

    users_root = data_dir / users_dir_name
    if not users_root.exists():
        return
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        try:
            user_id = int(user_dir.name)
        except ValueError:
            continue
        for stock_dir in user_dir.iterdir():
            if not stock_dir.is_dir():
                continue
            for filepath in stock_dir.glob("*.json"):
                yield user_id, stock_dir.name, filepath
            # versions/ 下是同日不可变快照，历史主列表仍按日期只展示当天最新别名。
            # 不遍历子目录，避免版本文件被索引成重复历史日期。


def rebuild_history_index(
    coordinator: HistoryIndexCoordinator,
    history_files: Iterable[HistoryFile],
    summary_loader: SummaryLoader,
    row_builder: HistoryRowBuilder,
    logger: logging.Logger,
) -> None:
    rows = []
    for scope_user_id, fallback_code, filepath in history_files:
        summary = summary_loader(filepath, fallback_code)
        if summary is not None:
            rows.append(row_builder(scope_user_id, filepath, summary))

    storage_root = coordinator.storage_root()

    def replace_rows(connection) -> None:
        connection.execute("DELETE FROM analysis_history_index WHERE storage_root = ?", (storage_root,))
        if rows:
            connection.executemany(_UPSERT_HISTORY_SQL, rows)

    coordinator.complete_rebuild(replace_rows)
    logger.info("分析历史索引重建完成: root=%s, rows=%s", storage_root, len(rows))


def query_history(
    coordinator: HistoryIndexCoordinator,
    user_id: int,
    code: str | None,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
    query: str | None = None,
) -> list[dict]:
    filters = ["h.storage_root = ?", "h.scope_user_id IN (0, ?)"]
    params: list[object] = [coordinator.storage_root(), user_id]
    if code is not None:
        filters.append("h.stock_code = ?")
        params.append(code)
    normalized_query = (query or "").strip().casefold()
    if normalized_query:
        filters.append("(LOWER(h.stock_code) LIKE ? OR LOWER(h.stock_name) LIKE ?)")
        pattern = f"%{normalized_query}%"
        params.extend((pattern, pattern))
    filters.append(
        """(
            h.scope_user_id = ? OR NOT EXISTS (
                SELECT 1 FROM analysis_history_index current_user
                WHERE current_user.storage_root = h.storage_root
                  AND current_user.scope_user_id = ?
                  AND current_user.stock_code = h.stock_code
                  AND current_user.analysis_date = h.analysis_date
            )
        )"""
    )
    params.extend((user_id, user_id, limit, offset))
    rows = get_connection().execute(
        f"""
        SELECT h.scope_user_id, h.stock_code, h.stock_name, h.analysis_date, h.current_price,
               h.overall_rating, h.signal, h.confidence
        FROM analysis_history_index h
        WHERE {' AND '.join(filters)}
        ORDER BY h.analysis_date DESC, h.stock_code DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        scope_user_id = item.pop("scope_user_id")
        item["can_delete"] = scope_user_id == user_id or can_delete_legacy
        items.append(item)
    return items
