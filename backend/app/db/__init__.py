import logging

from app.db.connection import get_connection
from app.db.schema import TABLES

logger = logging.getLogger(__name__)


def _migrate(conn) -> None:
    """Additive, idempotent column migrations for pre-existing databases.

    New tables get their full definition from CREATE TABLE above; existing tables
    need explicit ALTER TABLE to gain new columns.
    """
    user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if user_cols and "must_change_password" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
        logger.info("已迁移: users.must_change_password 列已补充")


def init_db() -> None:
    """启动时初始化 SQLite 数据库，创建所有表并执行增量迁移。

    Return:
        无。
    """
    conn = get_connection()
    for ddl in TABLES:
        conn.execute(ddl)
    _migrate(conn)
    conn.commit()
    logger.info("数据库表初始化完成")
