import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "market_data.db"

# 每线程一个 SQLite 连接：单一共享连接在多线程下并发执行多语句事务（execute
# + commit）不安全，事务会相互交错。WAL 模式原生支持多连接并发读写，因此改为
# 线程本地连接——每个线程的事务由 SQLite 自身隔离，无需全局写锁。
_local = threading.local()
_all_connections: list[sqlite3.Connection] = []
_registry_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    """获取当前线程专属的 SQLite 连接，首次调用时自动创建。

    Return:
        SQLite 连接对象（每个线程独立，WAL 模式下可安全并发）。
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-8000")  # 8 MB 缓存
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")  # 写锁竞争时最多等待 5s 而非立即报错
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        with _registry_lock:
            _all_connections.append(conn)
        logger.info(f"SQLite 线程连接已建立: {_DB_PATH} (thread={threading.get_ident()})")
    return conn


def close_connection():
    """关闭所有线程的 SQLite 连接并重置。"""
    with _registry_lock:
        conns = list(_all_connections)
        _all_connections.clear()
    for conn in conns:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception as exc:
            logger.warning(f"关闭 SQLite 连接失败: {exc}")
    _local.conn = None
    logger.info("SQLite 连接已全部关闭")


def reset_for_tests() -> None:
    """测试辅助：丢弃所有已注册连接与本线程连接，使下次 get_connection 重新建立。

    仅供测试在切换 _DB_PATH 后调用；跨线程连接对象无法在此线程安全关闭，故直接
    丢弃引用交由 GC 处理，不发出关闭告警。
    """
    with _registry_lock:
        _all_connections.clear()
    _local.conn = None


def checkpoint_wal():
    """主动触发 WAL checkpoint，控制 WAL 文件大小。"""
    try:
        get_connection().execute("PRAGMA wal_checkpoint(PASSIVE)")
    except Exception as exc:
        logger.warning(f"WAL checkpoint 失败: {exc}")
