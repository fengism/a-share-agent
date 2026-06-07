import logging

from app.db.connection import get_connection
from app.db.models import TABLES

logger = logging.getLogger(__name__)


def init_db() -> None:
    """启动时初始化 SQLite 数据库，创建所有表。

    Return:
        无。
    """
    conn = get_connection()
    for ddl in TABLES:
        conn.execute(ddl)
    conn.commit()
    logger.info("数据库表初始化完成")
