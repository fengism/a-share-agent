"""数据库连接、迁移与持久化实现。"""

import logging

from app.infrastructure.persistence.concept_stats import rebuild_concept_counts
from app.infrastructure.persistence.connection import database_path, get_connection, unit_of_work
from app.infrastructure.persistence.ddl import INDUSTRY_TABLES, MARKET_TABLES, USER_TABLES
from app.infrastructure.persistence.master_data_repair import backfill_industry_stock_names
from app.infrastructure.persistence.migrations import (
    INDUSTRY_MIGRATIONS,
    MARKET_MIGRATIONS,
    USER_MIGRATIONS,
    apply_migrations,
)
from app.infrastructure.persistence.seeds import seed_industry_database

logger = logging.getLogger(__name__)


def init_db() -> None:
    """启动时分别初始化市场库、用户库和行业库，并应用各自的结构迁移。

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

    industry_conn = get_connection("industry")
    for ddl in INDUSTRY_TABLES:
        industry_conn.execute(ddl)
    industry_conn.commit()
    apply_migrations(industry_conn, INDUSTRY_MIGRATIONS)
    seeded = seed_industry_database(industry_conn)
    if "stock_concept_mappings" not in seeded:
        with unit_of_work(connection=industry_conn, immediate=True):
            rebuild_concept_counts(industry_conn)
    repaired_names = backfill_industry_stock_names(industry_conn)
    if repaired_names:
        logger.info("行业股票名称补齐: %s 条", repaired_names)
    logger.info(
        "数据库表初始化完成: market=%s user=%s industry=%s",
        database_path("market"),
        database_path("user"),
        database_path("industry"),
    )
