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
    """启动时初始化核心业务库，并由专属仓储迁移独立日行情库。

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
    # 提前建好独立日行情库结构，再注册统一连接，避免启动后的首次在线备份
    # 抢在行情后台任务初始化之前生成一个空结构备份。
    from app.modules.market_daily.repository import MarketDailyBarRepository

    MarketDailyBarRepository(database_path("market_daily")).initialize()
    get_connection("market_daily")
    logger.info(
        "数据库表初始化完成: market=%s user=%s industry=%s market_daily=%s",
        database_path("market"),
        database_path("user"),
        database_path("industry"),
        database_path("market_daily"),
    )
