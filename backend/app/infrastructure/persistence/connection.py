from __future__ import annotations

import logging
import os
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from types import TracebackType
from typing import Literal

from app.configuration.paths import DATA_DIR
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

DatabaseName = Literal["market", "user", "industry"]
ALL_DATABASES: tuple[DatabaseName, ...] = ("market", "user", "industry")

_DATA_DIR = DATA_DIR
DB_DIR = _DATA_DIR / "db"
_DATABASE_FILENAMES: dict[DatabaseName, str] = {
    "market": "market_data.db",
    "user": "user_data.db",
    "industry": "industry_data.db",
}
_storage_migration_lock = threading.Lock()
_storage_migration_done = False

# 每线程一个 SQLite 连接：单一共享连接在多线程下并发执行多语句事务（execute
# + commit）不安全，事务会相互交错。WAL 模式原生支持多连接并发读写，因此改为
# 线程本地连接——每个线程的事务由 SQLite 自身隔离，无需全局写锁。
_local = threading.local()
_all_connections: list[sqlite3.Connection] = []
_connection_names: dict[int, str] = {}
_registry_lock = threading.Lock()
_connection_generation = 0


def _legacy_and_target_pairs(data_dir: Path, db_dir: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for filename in _DATABASE_FILENAMES.values():
        for suffix in ("", "-wal", "-shm"):
            pairs.append((data_dir / f"{filename}{suffix}", db_dir / f"{filename}{suffix}"))
    pairs.append((data_dir / "backups", db_dir / "backups"))
    return pairs


def migrate_legacy_database_storage(
    *,
    data_dir: Path = _DATA_DIR,
    db_dir: Path = DB_DIR,
) -> list[tuple[Path, Path]]:
    """Move legacy SQLite files into ``data/db`` without overwriting anything."""
    pairs = _legacy_and_target_pairs(data_dir, db_dir)
    conflicts = [(source, target) for source, target in pairs if source.exists() and target.exists()]
    if conflicts:
        details = ", ".join(f"{source} -> {target}" for source, target in conflicts)
        raise RuntimeError(f"数据库目录迁移冲突，拒绝覆盖已有文件: {details}")

    pending = [(source, target) for source, target in pairs if source.exists()]
    if not pending:
        return []
    db_dir.mkdir(parents=True, exist_ok=True)
    moved: list[tuple[Path, Path]] = []
    try:
        for source, target in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            moved.append((source, target))
            logger.info("旧数据库存储已迁移: source=%s target=%s", source, target)
    except Exception:
        rollback_errors: list[str] = []
        for source, target in reversed(moved):
            try:
                os.replace(target, source)
            except Exception as rollback_error:
                rollback_errors.append(f"{target} -> {source}: {rollback_error}")
        if rollback_errors:
            logger.critical("数据库目录迁移回滚不完整: %s", "; ".join(rollback_errors))
        raise
    return moved


def _ensure_database_storage_migrated() -> None:
    global _storage_migration_done
    if _storage_migration_done:
        return
    with _storage_migration_lock:
        if _storage_migration_done:
            return
        migrate_legacy_database_storage()
        _storage_migration_done = True


def database_path(database: DatabaseName = "market") -> Path:
    """返回指定逻辑数据库的文件路径。"""
    try:
        filename = _DATABASE_FILENAMES[database]
    except KeyError as error:
        raise ValueError(f"未知数据库: {database}") from error
    _ensure_database_storage_migrated()
    return DB_DIR / filename


def default_backup_dir() -> Path:
    """Return the unified default backup directory, migrating the legacy path first."""
    _ensure_database_storage_migrated()
    return DB_DIR / "backups"


def get_connection(database: DatabaseName = "market") -> sqlite3.Connection:
    """获取当前线程专属的 SQLite 连接，首次调用时自动创建。

    Return:
        SQLite 连接对象（每个线程独立，WAL 模式下可安全并发）。
    """
    connections = getattr(_local, "connections", None)
    if connections is None or getattr(_local, "generation", -1) != _connection_generation:
        connections = {}
        _local.connections = connections
        _local.generation = _connection_generation
    conn = connections.get(database)
    if conn is None:
        path = database_path(database)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-8000")  # 8 MB 缓存
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")  # 写锁竞争时最多等待 5s 而非立即报错
        conn.row_factory = sqlite3.Row
        connections[database] = conn
        with _registry_lock:
            _all_connections.append(conn)
            _connection_names[id(conn)] = database
        logger.info(
            "SQLite 线程连接已建立: database=%s path=%s thread=%s",
            database,
            path,
            threading.get_ident(),
        )
    return conn


def database_storage_snapshot(
    *,
    databases: tuple[DatabaseName, ...] = ALL_DATABASES,
    connection_provider: Callable[[DatabaseName], sqlite3.Connection] = get_connection,
    path_provider: Callable[[DatabaseName], Path] = database_path,
) -> dict[str, dict[str, int | float | str]]:
    """Collect a bounded read-only storage snapshot for each SQLite database."""
    snapshot: dict[str, dict[str, int | float | str]] = {}
    for database in databases:
        connection = connection_provider(database)
        path = path_provider(database)
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        freelist_count = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        wal_path = Path(f"{path}-wal")
        shm_path = Path(f"{path}-shm")
        snapshot[database] = {
            "file_bytes": path.stat().st_size if path.is_file() else 0,
            "wal_bytes": wal_path.stat().st_size if wal_path.is_file() else 0,
            "shm_bytes": shm_path.stat().st_size if shm_path.is_file() else 0,
            "page_count": page_count,
            "page_size": page_size,
            "freelist_count": freelist_count,
            "freelist_bytes": freelist_count * page_size,
            "freelist_ratio": round(freelist_count / page_count, 6) if page_count else 0.0,
            "journal_mode": journal_mode,
        }
    return snapshot


def _is_busy_error(error: BaseException | None) -> bool:
    if not isinstance(error, sqlite3.Error):
        return False
    error_code = getattr(error, "sqlite_errorcode", None)
    if isinstance(error_code, int) and error_code & 0xFF in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        return True
    message = str(error).lower()
    return "database is locked" in message or "database is busy" in message


class SQLiteUnitOfWork:
    """SQLite 事务边界，嵌套使用 SAVEPOINT，支持业务主动回滚。"""

    def __init__(self, connection: sqlite3.Connection, *, immediate: bool = False) -> None:
        self.connection = connection
        self._immediate = immediate
        self._rollback_only = False
        self._savepoint: str | None = None
        self._active = False
        self._started_at = 0.0
        with _registry_lock:
            self._database = _connection_names.get(id(connection), "external")

    def _record(self, error: BaseException | None) -> None:
        metrics.record_persistence_operation(
            self._database,
            "transaction",
            success=not isinstance(error, sqlite3.Error),
            duration_ms=(perf_counter() - self._started_at) * 1000,
            busy=_is_busy_error(error),
            error_type=type(error).__name__ if isinstance(error, sqlite3.Error) else None,
        )

    def __enter__(self) -> SQLiteUnitOfWork:
        if self._active:
            raise RuntimeError("Unit of Work 不可重复进入")
        self._active = True
        self._started_at = perf_counter()
        try:
            if self.connection.in_transaction:
                counter = getattr(_local, "savepoint_counter", 0) + 1
                _local.savepoint_counter = counter
                self._savepoint = f"uow_{counter}"
                self.connection.execute(f"SAVEPOINT {self._savepoint}")
            else:
                statement = "BEGIN IMMEDIATE" if self._immediate else "BEGIN"
                self.connection.execute(statement)
        except Exception as error:
            self._active = False
            self._record(error)
            raise
        return self

    def mark_rollback(self) -> None:
        if not self._active:
            raise RuntimeError("Unit of Work 尚未进入")
        self._rollback_only = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        should_rollback = exc_type is not None or self._rollback_only
        try:
            try:
                if self._savepoint is not None:
                    if should_rollback:
                        self.connection.execute(f"ROLLBACK TO SAVEPOINT {self._savepoint}")
                    self.connection.execute(f"RELEASE SAVEPOINT {self._savepoint}")
                elif should_rollback:
                    self.connection.rollback()
                else:
                    self.connection.commit()
            except Exception as transaction_error:
                self._record(transaction_error)
                raise
            self._record(exc)
        finally:
            self._active = False
        return False


def unit_of_work(
    database: DatabaseName = "market",
    *,
    immediate: bool = False,
    connection: sqlite3.Connection | None = None,
) -> SQLiteUnitOfWork:
    return SQLiteUnitOfWork(
        connection if connection is not None else get_connection(database),
        immediate=immediate,
    )


def close_connection():
    """关闭所有线程的 SQLite 连接并重置。"""
    global _connection_generation
    with _registry_lock:
        conns = list(_all_connections)
        _all_connections.clear()
        for conn in conns:
            _connection_names.pop(id(conn), None)
        _connection_generation += 1
    checkpointed_paths: set[str] = set()
    for conn in conns:
        try:
            main_row = next(row for row in conn.execute("PRAGMA database_list") if row[1] == "main")
            database_file = str(main_row[2])
            if database_file in checkpointed_paths:
                continue
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            checkpointed_paths.add(database_file)
        except Exception as exc:
            logger.warning("关闭前 WAL checkpoint 失败: %s", exc)
    for conn in conns:
        try:
            conn.close()
        except Exception as exc:
            logger.warning(f"关闭 SQLite 连接失败: {exc}")
    _local.connections = {}
    _local.generation = _connection_generation
    _local.savepoint_counter = 0
    logger.info("SQLite 连接已全部关闭")


def reset_for_tests() -> None:
    """测试辅助：关闭连接并重置一次性存储迁移状态。"""
    global _storage_migration_done
    close_connection()
    with _storage_migration_lock:
        _storage_migration_done = False


def checkpoint_wal() -> dict[str, dict[str, int | bool | str]]:
    """主动触发两个数据库的 WAL checkpoint，控制 WAL 文件大小。"""
    snapshot: dict[str, dict[str, int | bool | str]] = {}
    for database in ALL_DATABASES:
        started_at = perf_counter()
        try:
            row = get_connection(database).execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            busy = int(row[0])
            log_frames = int(row[1])
            checkpointed_frames = int(row[2])
            pending = busy > 0 or checkpointed_frames < log_frames
            metrics.record_persistence_operation(
                database,
                "wal_checkpoint",
                success=True,
                duration_ms=(perf_counter() - started_at) * 1000,
                busy=busy > 0,
                processed=checkpointed_frames,
                pending=pending,
            )
            snapshot[database] = {
                "busy": busy,
                "log_frames": log_frames,
                "checkpointed_frames": checkpointed_frames,
                "pending": pending,
            }
        except Exception as exc:
            metrics.record_persistence_operation(
                database,
                "wal_checkpoint",
                success=False,
                duration_ms=(perf_counter() - started_at) * 1000,
                busy=_is_busy_error(exc),
                error_type=type(exc).__name__,
            )
            snapshot[database] = {"error": type(exc).__name__}
            logger.warning("WAL checkpoint 失败: database=%s error=%s", database, exc)
    return snapshot


def optimize_databases() -> dict[str, dict[str, bool | int | str]]:
    """执行 SQLite 推荐的轻量统计优化，不重建数据库文件。"""
    snapshot: dict[str, dict[str, bool | int | str]] = {}
    for database in ALL_DATABASES:
        started_at = perf_counter()
        try:
            rows = get_connection(database).execute("PRAGMA optimize").fetchall()
            metrics.record_persistence_operation(
                database,
                "optimize",
                success=True,
                duration_ms=(perf_counter() - started_at) * 1000,
                processed=len(rows),
            )
            snapshot[database] = {"success": True, "result_rows": len(rows)}
        except Exception as exc:
            metrics.record_persistence_operation(
                database,
                "optimize",
                success=False,
                duration_ms=(perf_counter() - started_at) * 1000,
                busy=_is_busy_error(exc),
                error_type=type(exc).__name__,
            )
            snapshot[database] = {"success": False, "error": type(exc).__name__}
            logger.warning("SQLite optimize 失败: database=%s error=%s", database, exc)
    return snapshot
