import logging
import sqlite3
import threading
from collections.abc import Callable, Sequence

from app.infrastructure.persistence.connection import database_path, get_connection, unit_of_work
from app.infrastructure.persistence.ddl import HISTORY_INDEX_STATE_TABLE

RebuildCallback = Callable[[], None]
IndexWriter = Callable[[sqlite3.Connection], None]


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

    def ensure_schema(self) -> None:
        current_database_path = str(database_path("market").resolve())
        if current_database_path in self.schema_databases:
            return
        with self.schema_lock:
            if current_database_path in self.schema_databases:
                return
            with unit_of_work() as work:
                work.connection.execute(HISTORY_INDEX_STATE_TABLE)
                for ddl in self._schema_ddl:
                    work.connection.execute(ddl)
            self.schema_databases.add(current_database_path)

    def write(self, writer: IndexWriter) -> None:
        """串行执行增量索引写入，避免与全量重建交错。"""
        with self.index_lock:
            self.ensure_schema()
            with unit_of_work() as work:
                writer(work.connection)

    def complete_rebuild(self, writer: IndexWriter) -> None:
        """原子替换索引数据并记录重建完成状态。"""
        with self.index_lock:
            self.ensure_schema()
            with unit_of_work() as work:
                writer(work.connection)
                work.connection.execute(
                    """
                    INSERT INTO history_index_state(kind, storage_root, completed_at)
                    VALUES (?, ?, datetime('now','localtime'))
                    ON CONFLICT(kind, storage_root) DO UPDATE SET completed_at = excluded.completed_at
                    """,
                    (self.kind, self.storage_root()),
                )
            self.indexed_roots.add(self.index_key())

    def rebuild(self, callback: RebuildCallback) -> None:
        with self.index_lock:
            callback()

    def ensure(self, rebuild_callback: RebuildCallback) -> None:
        key = self.index_key()
        if key in self.indexed_roots:
            return
        with self.index_lock:
            key = self.index_key()
            if key in self.indexed_roots:
                return
            self.ensure_schema()
            indexed = get_connection().execute(
                "SELECT 1 FROM history_index_state WHERE kind = ? AND storage_root = ?",
                (self.kind, self.storage_root()),
            ).fetchone()
            if indexed:
                self.indexed_roots.add(key)
                return
            rebuild_callback()

    def mark_dirty(self) -> None:
        with self.index_lock:
            self.indexed_roots.discard(self.index_key())
            try:
                self.ensure_schema()
                with unit_of_work() as work:
                    work.connection.execute(
                        "DELETE FROM history_index_state WHERE kind = ? AND storage_root = ?",
                        (self.kind, self.storage_root()),
                    )
            except Exception:
                self._logger.warning("清理%s历史索引状态失败", self._label, exc_info=True)
