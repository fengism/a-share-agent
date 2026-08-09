"""数据库连接、迁移与持久化实现。"""

import logging

from app.infrastructure.persistence.connection import database_path, get_connection
from app.infrastructure.persistence.ddl import MARKET_TABLES, USER_TABLES
from app.infrastructure.persistence.migrations import MARKET_MIGRATIONS, USER_MIGRATIONS, apply_migrations

logger = logging.getLogger(__name__)


def init_db() -> None:
    """启动时分别初始化市场库和用户库，并应用各自的结构迁移。

    Return:
        无。
    """
    market_conn = get_connection("market")
    for ddl in MARKET_TABLES:
        market_conn.execute(ddl)
    market_conn.commit()
    apply_migrations(market_conn, MARKET_MIGRATIONS)

    user_conn = get_connection("user")
    for ddl in USER_TABLES:
        user_conn.execute(ddl)
    user_conn.commit()
    apply_migrations(user_conn, USER_MIGRATIONS)
    logger.info(
        "数据库表初始化完成: market=%s user=%s",
        database_path("market"),
        database_path("user"),
    )
