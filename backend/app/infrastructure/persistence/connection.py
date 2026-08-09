from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from types import TracebackType
from typing import Literal

from app.configuration.paths import DATA_DIR

logger = logging.getLogger(__name__)

DatabaseName = Literal["market", "user"]

_DATA_DIR = DATA_DIR
_DB_PATH = _DATA_DIR / "market_data.db"
_USER_DB_PATH = _DATA_DIR / "user_data.db"

# 每线程一个 SQLite 连接：单一共享连接在多线程下并发执行多语句事务（execute
# + commit）不安全，事务会相互交错。WAL 模式原生支持多连接并发读写，因此改为
# 线程本地连接——每个线程的事务由 SQLite 自身隔离，无需全局写锁。
_local = threading.local()
_all_connections: list[sqlite3.Connection] = []
_registry_lock = threading.Lock()
_connection_generation = 0


def database_path(database: DatabaseName = "market") -> Path:
    """返回指定逻辑数据库的文件路径。"""
    if database == "market":
        return _DB_PATH
    if database == "user":
        return _USER_DB_PATH
    raise ValueError(f"未知数据库: {database}")


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
        logger.info(
            "SQLite 线程连接已建立: database=%s path=%s thread=%s",
            database,
            path,
            threading.get_ident(),
        )
    return conn


class SQLiteUnitOfWork:
    """SQLite 事务边界，嵌套使用 SAVEPOINT，支持业务主动回滚。"""

    def __init__(self, connection: sqlite3.Connection, *, immediate: bool = False) -> None:
        self.connection = connection
        self._immediate = immediate
        self._rollback_only = False
        self._savepoint: str | None = None
        self._active = False

    def __enter__(self) -> SQLiteUnitOfWork:
        if self._active:
            raise RuntimeError("Unit of Work 不可重复进入")
        self._active = True
        if self.connection.in_transaction:
            counter = getattr(_local, "savepoint_counter", 0) + 1
            _local.savepoint_counter = counter
            self._savepoint = f"uow_{counter}"
            self.connection.execute(f"SAVEPOINT {self._savepoint}")
        else:
            statement = "BEGIN IMMEDIATE" if self._immediate else "BEGIN"
            self.connection.execute(statement)
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
            if self._savepoint is not None:
                if should_rollback:
                    self.connection.execute(f"ROLLBACK TO SAVEPOINT {self._savepoint}")
                self.connection.execute(f"RELEASE SAVEPOINT {self._savepoint}")
            elif should_rollback:
                self.connection.rollback()
            else:
                self.connection.commit()
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
    """测试辅助：关闭全部连接，使下次 get_connection 使用当前测试数据库路径。"""
    close_connection()


def checkpoint_wal():
    """主动触发两个数据库的 WAL checkpoint，控制 WAL 文件大小。"""
    for database in ("market", "user"):
        try:
            get_connection(database).execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception as exc:
            logger.warning("WAL checkpoint 失败: database=%s error=%s", database, exc)
