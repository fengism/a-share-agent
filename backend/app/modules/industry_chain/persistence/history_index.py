"""产业链历史索引存储。"""

import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path

from app.infrastructure.persistence.connection import get_connection
from app.infrastructure.persistence.history_index import HistoryIndexCoordinator
from app.modules.industry_chain.schemas import IndustryChainHistoryItem

SafeNameFunc = Callable[[str], str]
LoadHistoryItemFunc = Callable[[Path, Path], IndustryChainHistoryItem | None]

_UPSERT_HISTORY_SQL = """
INSERT INTO industry_chain_history_index (
    storage_root, scope_user_id, safe_name, name, archive_id,
    saved_at, title, summary, file_path
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(storage_root, scope_user_id, safe_name, archive_id) DO UPDATE SET
    name = excluded.name,
    saved_at = excluded.saved_at,
    title = excluded.title,
    summary = excluded.summary,
    file_path = excluded.file_path
"""


def history_roots(base_dir: Path, name: str | None, safe_name_func: SafeNameFunc) -> list[Path]:
    if name:
        return [base_dir / safe_name_func(name)]
    if not base_dir.exists():
        return []
    return [path for path in base_dir.iterdir() if path.is_dir() and path.name != "users"]


def history_item_from_payload(
    payload: dict,
    root: Path,
    fallback_archive_id: str,
) -> IndustryChainHistoryItem:
    original_name = payload.get("name") or root.name
    result_data = payload.get("result", {})
    summary = result_data.get("summary") or result_data.get("llm_review", "")[:80]
    return IndustryChainHistoryItem(
        name=original_name,
        archive_id=payload.get("archive_id") or fallback_archive_id,
        saved_at=payload.get("saved_at", ""),
        title=f"{original_name} 产业链分析",
        summary=summary.strip(),
        can_delete=False,
    )


def load_history_item(
    path: Path,
    root: Path,
    logger: logging.Logger,
) -> IndustryChainHistoryItem | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return history_item_from_payload(payload, root, path.stem)
    except Exception as exc:
        logger.warning("跳过失效的产业链历史文件: %s, error=%s", path, exc)
        return None


def history_row(
    coordinator: HistoryIndexCoordinator,
    scope_user_id: int,
    safe_name: str,
    path: Path,
    item: IndustryChainHistoryItem,
) -> tuple[object, ...]:
    return (
        coordinator.storage_root(),
        scope_user_id,
        safe_name,
        item.name,
        item.archive_id,
        item.saved_at,
        item.title,
        item.summary,
        str(path),
    )


def upsert_history_item(
    coordinator: HistoryIndexCoordinator,
    scope_user_id: int,
    safe_name: str,
    path: Path,
    item: IndustryChainHistoryItem,
) -> None:
    row = history_row(coordinator, scope_user_id, safe_name, path, item)
    coordinator.write(lambda connection: connection.execute(_UPSERT_HISTORY_SQL, row))


def delete_history_item(
    coordinator: HistoryIndexCoordinator,
    scope_user_id: int,
    safe_name: str,
    archive_id: str,
) -> None:
    coordinator.write(
        lambda connection: connection.execute(
            """
            DELETE FROM industry_chain_history_index
            WHERE storage_root = ? AND scope_user_id = ?
              AND safe_name = ? AND archive_id = ?
            """,
            (coordinator.storage_root(), scope_user_id, safe_name, archive_id),
        )
    )


def iter_history_files(
    data_dir: Path,
    safe_name_func: SafeNameFunc,
) -> Iterator[tuple[int, Path, Path]]:
    for root in history_roots(data_dir, None, safe_name_func):
        for path in root.glob("*.json"):
            yield 0, root, path

    users_root = data_dir / "users"
    if not users_root.exists():
        return
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        try:
            user_id = int(user_dir.name)
        except ValueError:
            continue
        for root in history_roots(user_dir, None, safe_name_func):
            for path in root.glob("*.json"):
                yield user_id, root, path


def rebuild_history_index_locked(
    coordinator: HistoryIndexCoordinator,
    data_dir: Path,
    safe_name_func: SafeNameFunc,
    load_item_func: LoadHistoryItemFunc,
    logger: logging.Logger,
) -> None:
    coordinator.ensure_schema()
    rows = []
    for scope_user_id, root, path in iter_history_files(data_dir, safe_name_func):
        item = load_item_func(path, root)
        if item is not None:
            rows.append(history_row(coordinator, scope_user_id, root.name, path, item))

    storage_root = coordinator.storage_root()

    def replace_rows(connection) -> None:
        connection.execute("DELETE FROM industry_chain_history_index WHERE storage_root = ?", (storage_root,))
        if rows:
            connection.executemany(_UPSERT_HISTORY_SQL, rows)

    coordinator.complete_rebuild(replace_rows)
    logger.info("产业链历史索引重建完成: root=%s, rows=%s", storage_root, len(rows))


def rebuild_history_index(
    coordinator: HistoryIndexCoordinator,
    data_dir: Path,
    safe_name_func: SafeNameFunc,
    load_item_func: LoadHistoryItemFunc,
    logger: logging.Logger,
) -> None:
    coordinator.rebuild(
        lambda: rebuild_history_index_locked(
            coordinator,
            data_dir,
            safe_name_func,
            load_item_func,
            logger,
        )
    )


def ensure_history_index(
    coordinator: HistoryIndexCoordinator,
    data_dir: Path,
    safe_name_func: SafeNameFunc,
    load_item_func: LoadHistoryItemFunc,
    logger: logging.Logger,
) -> None:
    coordinator.ensure(
        lambda: rebuild_history_index_locked(
            coordinator,
            data_dir,
            safe_name_func,
            load_item_func,
            logger,
        )
    )


def list_history(
    coordinator: HistoryIndexCoordinator,
    data_dir: Path,
    safe_name_func: SafeNameFunc,
    load_item_func: LoadHistoryItemFunc,
    logger: logging.Logger,
    user_id: int,
    name: str | None,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
) -> list[IndustryChainHistoryItem]:
    ensure_history_index(coordinator, data_dir, safe_name_func, load_item_func, logger)
    filters = ["h.storage_root = ?", "h.scope_user_id IN (0, ?)"]
    params: list[object] = [coordinator.storage_root(), user_id]
    if name:
        filters.append("h.safe_name = ?")
        params.append(safe_name_func(name))
    filters.append(
        """(
            h.scope_user_id = ? OR NOT EXISTS (
                SELECT 1 FROM industry_chain_history_index current_user
                WHERE current_user.storage_root = h.storage_root
                  AND current_user.scope_user_id = ?
                  AND current_user.safe_name = h.safe_name
                  AND current_user.archive_id = h.archive_id
            )
        )"""
    )
    params.extend((user_id, user_id, limit, offset))
    rows = get_connection().execute(
        f"""
        SELECT h.scope_user_id, h.name, h.archive_id, h.saved_at, h.title, h.summary
        FROM industry_chain_history_index h
        WHERE {' AND '.join(filters)}
        ORDER BY h.archive_id DESC, h.safe_name DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        scope_user_id = item.pop("scope_user_id")
        item["can_delete"] = scope_user_id == user_id or can_delete_legacy
        items.append(IndustryChainHistoryItem.model_validate(item))
    return sorted(
        items,
        key=lambda item: (item.saved_at, item.archive_id),
        reverse=True,
    )
