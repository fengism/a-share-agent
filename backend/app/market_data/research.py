"""Provider-backed research capabilities shared by Agent tools."""

from typing import Any

from app.infrastructure.providers.iwencai_runtime import (
    iwencai_market_macro as _iwencai_market_macro,
)
from app.infrastructure.providers.iwencai_runtime import iwencai_query as _iwencai_query
from app.infrastructure.providers.iwencai_runtime import iwencai_search as _iwencai_search
from app.infrastructure.providers.iwencai_runtime import (
    iwencai_select_stock as _iwencai_select_stock,
)


async def iwencai_market_macro(query: str, limit: int = 20) -> Any:
    return await _iwencai_market_macro(query, limit=limit)


async def iwencai_query(query: str, limit: int = 30) -> Any:
    return await _iwencai_query(query, limit=limit)


async def iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    return await _iwencai_search(query, channel=channel, size=size)


async def iwencai_select_stock(query: str, limit: int = 20) -> Any:
    return await _iwencai_select_stock(query, limit=limit)
