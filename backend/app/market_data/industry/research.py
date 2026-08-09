"""Provider-backed industry research primitives."""

from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.infrastructure.providers.iwencai_runtime import (
    iwencai_query,
    iwencai_search,
    iwencai_select_stock,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_EASTMONEY_OPERATIONS = {
    "search_stocks": "search_stocks",
    "industry_rankings": "fetch_industry_rankings",
    "concept_rankings": "fetch_concept_rankings",
    "industry_fund_flow": "fetch_industry_fund_flow",
    "concept_fund_flow": "fetch_concept_fund_flow",
    "industry_components": "fetch_industry_components",
}


async def query_industry_data(query: str, limit: int = 50) -> Any:
    return await iwencai_query(query, limit=limit)


async def search_industry_content(
    query: str,
    channel: str = "news",
    size: int = 20,
) -> Any:
    return await iwencai_search(query, channel=channel, size=size)


async def select_industry_stocks(query: str, limit: int = 50) -> Any:
    return await iwencai_select_stock(query, limit=limit)


async def call_eastmoney_industry(operation: str, *args: Any) -> Any:
    method_name = _EASTMONEY_OPERATIONS.get(operation)
    if method_name is None:
        raise ValueError(f"不支持的产业数据操作: {operation}")
    provider = get_provider("eastmoney")
    return await provider_gateway.call(
        "eastmoney",
        operation,
        lambda: call_blocking(
            getattr(provider, method_name),
            *args,
            semaphore=eastmoney_semaphore,
        ),
        is_fallback_attempt=True,
        max_attempts=1,
    )
