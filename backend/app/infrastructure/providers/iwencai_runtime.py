"""问财 Provider 的异步调用治理与业务查询入口。"""

from typing import Any

from app.configuration import get_effective_settings
from app.core.concurrency.rate_limiter import call_blocking, iwencai_semaphore
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider


def _get_iwencai_provider():
    settings = get_effective_settings()
    if not settings.iwencai_enabled:
        return None
    return get_provider("iwencai")


async def iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    """搜索研报、公告或新闻，并统一应用 Provider 治理策略。"""
    size = int(size)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    if channel == "news":
        result = await provider_gateway.call(
            "iwencai",
            "search_news",
            lambda: call_blocking(
                iwencai_provider.search_news,
                query,
                size,
                semaphore=iwencai_semaphore,
            ),
        )
        return [item.model_dump() for item in result[:size]]
    result = await provider_gateway.call(
        "iwencai",
        "search",
        lambda: call_blocking(
            iwencai_provider.search,
            query,
            channel,
            size,
            semaphore=iwencai_semaphore,
        ),
    )
    return iwencai_provider.dedup_articles(result)[:size]


async def iwencai_query(query: str, limit: int = 30) -> Any:
    """执行非选股类自然语言结构化查询。"""
    limit = int(limit)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await provider_gateway.call(
        "iwencai",
        "query_stock_data",
        lambda: call_blocking(
            iwencai_provider.query_stock_data,
            query,
            1,
            limit,
            semaphore=iwencai_semaphore,
        ),
    )


async def iwencai_select_stock(query: str, limit: int = 20) -> Any:
    """执行自然语言选股查询。"""
    limit = int(limit)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await provider_gateway.call(
        "iwencai",
        "select_stocks",
        lambda: call_blocking(
            iwencai_provider.select_stocks,
            query,
            1,
            limit,
            semaphore=iwencai_semaphore,
        ),
    )


async def iwencai_market_macro(query: str, limit: int = 20) -> Any:
    """执行自然语言宏观经济数据查询。"""
    limit = int(limit)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await provider_gateway.call(
        "iwencai",
        "query_market_macro",
        lambda: call_blocking(
            iwencai_provider.query_market_macro,
            query,
            1,
            limit,
            semaphore=iwencai_semaphore,
        ),
    )
