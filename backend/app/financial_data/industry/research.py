"""Provider-backed industry research primitives."""

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from app.core.concurrency.rate_limiter import baidu_semaphore, call_blocking, eastmoney_semaphore
from app.infrastructure.providers.iwencai_runtime import (
    iwencai_query,
    iwencai_search,
    iwencai_select_stock,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_PROVIDER_OPERATIONS = {
    "search_stocks": "search_stocks",
    "industry_rankings": "fetch_industry_rankings",
    "concept_rankings": "fetch_concept_rankings",
    "industry_fund_flow": "fetch_industry_fund_flow",
    "concept_fund_flow": "fetch_concept_fund_flow",
    "industry_components": "fetch_industry_components",
}
_INDEPENDENT_FIRST_OPERATIONS = {
    "industry_rankings",
    "concept_rankings",
    "industry_fund_flow",
    "concept_fund_flow",
}
_PROVIDER_SEMAPHORES = {
    "baidu": baidu_semaphore,
    "eastmoney": eastmoney_semaphore,
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


def _has_provider_data(operation: str, value: Any) -> bool:
    if isinstance(value, pd.DataFrame):
        return not value.empty
    if operation.endswith("rankings") and isinstance(value, Mapping):
        return bool(value.get("top") or value.get("bottom"))
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return value is not None


async def _call_provider_operation(
    provider_name: str,
    operation: str,
    method_name: str,
    *args: Any,
    is_fallback_attempt: bool = False,
) -> Any:
    provider = get_provider(provider_name)
    result = await provider_gateway.call(
        provider_name,
        operation,
        lambda: call_blocking(
            getattr(provider, method_name),
            *args,
            semaphore=_PROVIDER_SEMAPHORES[provider_name],
        ),
        is_fallback_attempt=is_fallback_attempt,
        max_attempts=1,
    )
    if not _has_provider_data(operation, result):
        raise ValueError(f"{provider_name} {operation} 返回空数据")
    return result


async def call_industry_data(operation: str, *args: Any) -> Any:
    """Call independent industry sources first, retaining EastMoney as fallback."""
    method_name = _PROVIDER_OPERATIONS.get(operation)
    if method_name is None:
        raise ValueError(f"不支持的产业链数据操作: {operation}")
    provider_names = (
        ("baidu", "eastmoney")
        if operation in _INDEPENDENT_FIRST_OPERATIONS
        else ("eastmoney",)
    )
    last_error: Exception | None = None
    for index, provider_name in enumerate(provider_names):
        try:
            return await _call_provider_operation(
                provider_name,
                operation,
                method_name,
                *args,
                is_fallback_attempt=index > 0,
            )
        except Exception as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"产业链数据源为空: {operation}")


async def call_eastmoney_industry(operation: str, *args: Any) -> Any:
    """Compatibility entry for callers that explicitly require EastMoney."""
    method_name = _PROVIDER_OPERATIONS.get(operation)
    if method_name is None:
        raise ValueError(f"不支持的东方财富操作: {operation}")
    return await _call_provider_operation(
        "eastmoney",
        operation,
        method_name,
        *args,
        is_fallback_attempt=True,
    )
