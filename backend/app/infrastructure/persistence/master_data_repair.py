"""从同库的个股资料补齐行业名称；只填空值，保留既有分类、名称与手工锁定。"""

import sqlite3

from app.infrastructure.persistence.connection import unit_of_work


def backfill_industry_stock_names(connection: sqlite3.Connection) -> int:
    with unit_of_work(connection=connection, immediate=True) as work:
        cursor = work.connection.execute(
            """
            UPDATE sw_industry_classifications AS industry
            SET stock_name = (
                SELECT profile.stock_name FROM stock_basic_profiles AS profile
                WHERE profile.stock_code = industry.stock_code
            ), updated_at = datetime('now','localtime')
            WHERE TRIM(industry.stock_name) = ''
              AND EXISTS (
                SELECT 1 FROM stock_basic_profiles AS profile
                WHERE profile.stock_code = industry.stock_code AND TRIM(profile.stock_name) <> ''
              )
            """
        )
        return cursor.rowcount
