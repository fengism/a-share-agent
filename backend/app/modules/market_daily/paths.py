"""独立日行情库路径。"""

from app.infrastructure.persistence.connection import database_path

MARKET_DAILY_DATABASE_PATH = database_path("market_daily")
