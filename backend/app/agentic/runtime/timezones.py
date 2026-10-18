"""Market timezone owned by the agent runtime (no app.core dependency)."""

from __future__ import annotations

from zoneinfo import ZoneInfo

SHANGHAI_TIMEZONE_NAME = "Asia/Shanghai"
SHANGHAI_TIMEZONE = ZoneInfo(SHANGHAI_TIMEZONE_NAME)

__all__ = ["SHANGHAI_TIMEZONE", "SHANGHAI_TIMEZONE_NAME"]
