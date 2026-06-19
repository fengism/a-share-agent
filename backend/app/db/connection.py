import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "market_data.db"
_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """获取全局复用的 SQLite 数据库连接，首次调用时自动创建。

    Return:
        SQLite 连接对象。
    """
    global _connection
    if _connection is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA synchronous=NORMAL")
        _connection.execute("PRAGMA cache_size=-8000")  # 8 MB 缓存
        _connection.execute("PRAGMA temp_store=MEMORY")
        _connection.execute("PRAGMA foreign_keys=ON")
        _connection.row_factory = sqlite3.Row
        logger.info(f"SQLite 连接已建立: {_DB_PATH}")
    return _connection


def close_connection():
    """关闭全局 SQLite 连接并重置为 None。"""
    global _connection
    if _connection is not None:
        _connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        _connection.close()
        _connection = None
        logger.info("SQLite 连接已关闭")


def checkpoint_wal():
    """主动触发 WAL checkpoint，控制 WAL 文件大小。"""
    global _connection
    if _connection is not None:
        try:
            _connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception as exc:
            logger.warning(f"WAL checkpoint 失败: {exc}")
