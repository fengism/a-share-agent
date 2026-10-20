"""市场时间基准（转发 domain 的权威定义）。

实际的常量与 ``market_today()`` 在 :mod:`app.domain.timezones`：domain 位于最底层，
核心包（``app.agentic``）与宿主都必须能依赖它，而这些常量放在 core 会让 domain
反向依赖 core。这里保留模块与同名导出，避免改动 20+ 处既有 import。
"""

from __future__ import annotations

from app.domain.timezones import (
    SHANGHAI_TIMEZONE,
    SHANGHAI_TIMEZONE_NAME,
    market_today,
)

__all__ = ["SHANGHAI_TIMEZONE", "SHANGHAI_TIMEZONE_NAME", "market_today"]
