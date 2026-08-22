import logging
import sqlite3
import threading
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from app.infrastructure.persistence.connection import database_path, get_connection, unit_of_work
from app.infrastructure.persistence.ddl import HISTORY_INDEX_STATE_TABLE
from app.infrastructure.persistence.json_storage import atomic_write_text

RebuildCallback = Callable[[], None]
IndexWriter = Callable[[sqlite3.Connection], None]


@dataclass
class HistoryIndexMutation:
    """Tracks whether both the archive and its SQLite summary were updated."""

    completed: bool = False

    def complete(self) -> None:
        self.completed = True


class HistoryIndexCoordinator:
    """协调文件历史索引的建表、首次回填和失效状态。"""

    def __init__(
        self,
        *,
        kind: str,
        storage_root: Callable[[], str],
        schema_ddl: Sequence[str],
        label: str,
        logger: logging.Logger,
    ) -> None:
        self.kind = kind
        self._storage_root = storage_root
        self._schema_ddl = tuple(schema_ddl)
        self._label = label
        self._logger = logger
        self.index_lock = threading.RLock()
        self.schema_lock = threading.Lock()
        self.indexed_roots: set[tuple[str, str]] = set()
        self.schema_databases: set[str] = set()

    def storage_root(self) -> str:
        return self._storage_root()

    def index_key(self) -> tuple[str, str]:
        return self.storage_root(), str(database_path("market").resolve())

    def dirty_marker_path(self) -> Path:
        return Path(self.storage_root()) / f".history-index-{self.kind}.dirty"

    def _state_row(self) -> sqlite3.Row | None:
        return get_connection().execute(
            "SELECT completed_at FROM history_index_state WHERE kind = ? AND storage_root = ?",
            (self.kind, self.storage_root()),
        ).fetchone()

    def _create_dirty_marker(self) -> None:
        atomic_write_text(self.dirty_marker_path(), f"{self.kind}\n")

    def _clear_dirty_marker(self) -> None:
        self.dirty_marker_path().unlink(missing_ok=True)

    def _invalidate_ready_state(self) -> None:
        self.indexed_roots.discard(self.index_key())
        try:
            self.ensure_schema()
            connection = get_connection()
            with unit_of_work(connection=connection) as work:
                work.connection.execute(
                    "DELETE FROM history_index_state WHERE kind = ? AND storage_root = ?",
                    (self.kind, self.storage_root()),
                )
        except Exception:
            self._logger.warning("清理%s历史索引状态失败", self._label, exc_info=True)

    def _complete_mutation(self) -> None:
        try:
            indexed = self._state_row() is not None
            self._clear_dirty_marker()
            if indexed:
                self.indexed_roots.add(self.index_key())
        except Exception:
            self._invalidate_ready_state()
            self._logger.warning("完成%s历史索引变更失败，保留脏状态", self._label, exc_info=True)

    @contextmanager
    def mutation(self) -> Iterator[HistoryIndexMutation]:
        """Guard one archive/index dual write with a durable dirty marker."""
        with self.index_lock:
            dirty_before_mutation = self.dirty_marker_path().exists()
            self._create_dirty_marker()
            self.indexed_roots.discard(self.index_key())
            mutation = HistoryIndexMutation()
            try:
                yield mutation
            except BaseException:
                self._invalidate_ready_state()
                raise
            if mutation.completed and not dirty_before_mutation:
                self._complete_mutation()
            else:
                self._invalidate_ready_state()

    def ensure_schema(self) -> None:
        current_database_path = str(database_path("market").resolve())
        if current_database_path in self.schema_databases:
            return
        with self.schema_lock:
            if current_database_path in self.schema_databases:
                return
            connection = get_connection()
            with unit_of_work(connection=connection) as work:
                work.connection.execute(HISTORY_INDEX_STATE_TABLE)
                for ddl in self._schema_ddl:
                    work.connection.execute(ddl)
            self.schema_databases.add(current_database_path)

    def write(self, writer: IndexWriter) -> None:
        """串行执行增量索引写入，避免与全量重建交错。"""
        with self.index_lock:
            self.ensure_schema()
            connection = get_connection()
            with unit_of_work(connection=connection) as work:
                writer(work.connection)

    def complete_rebuild(self, writer: IndexWriter) -> None:
        """原子替换索引数据并记录重建完成状态。"""
        with self.index_lock:
            self.ensure_schema()
            connection = get_connection()
            with unit_of_work(connection=connection) as work:
                writer(work.connection)
                work.connection.execute(
                    """
                    INSERT INTO history_index_state(kind, storage_root, completed_at)
                    VALUES (?, ?, datetime('now','localtime'))
                    ON CONFLICT(kind, storage_root) DO UPDATE SET completed_at = excluded.completed_at
                    """,
                    (self.kind, self.storage_root()),
                )
            self._clear_dirty_marker()
            self.indexed_roots.add(self.index_key())

    def rebuild(self, callback: RebuildCallback) -> None:
        with self.index_lock:
            callback()

    def ensure(self, rebuild_callback: RebuildCallback) -> None:
        key = self.index_key()
        if not self.dirty_marker_path().exists() and key in self.indexed_roots:
            return
        with self.index_lock:
            key = self.index_key()
            dirty = self.dirty_marker_path().exists()
            if not dirty and key in self.indexed_roots:
                return
            self.ensure_schema()
            if dirty:
                rebuild_callback()
                return
            indexed = self._state_row()
            if indexed:
                self.indexed_roots.add(key)
                return
            rebuild_callback()

    def mark_dirty(self) -> None:
        with self.index_lock:
            self._create_dirty_marker()
            self._invalidate_ready_state()

    def snapshot(self) -> dict[str, Any]:
        with self.index_lock:
            dirty = self.dirty_marker_path().exists()
            row = None
            try:
                self.ensure_schema()
                row = self._state_row()
            except Exception:
                self._logger.warning("读取%s历史索引状态失败", self._label, exc_info=True)
            indexed_in_process = self.index_key() in self.indexed_roots
            return {
                "ready": row is not None and not dirty,
                "dirty": dirty,
                "indexed_in_process": indexed_in_process,
                "completed_at": row["completed_at"] if row is not None else None,
            }
