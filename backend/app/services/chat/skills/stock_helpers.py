from __future__ import annotations

from typing import Any

from app.utils.rate_limiter import call_blocking


async def search_stocks(query: str) -> Any:
    from app.services.stock.search import search_stocks as _search_stocks
    result = await _search_stocks(query)
    return [item.model_dump() for item in result]


async def get_stock_info(code: str) -> Any:
    from app.services.stock.basic_info import get_basic_info
    result = await get_basic_info(code)
    return result.model_dump()


async def get_stock_valuation_detail(code: str) -> Any:
    from app.services.screener.percentiles import _compute_percentile
    from app.services.stock.valuation import get_valuation_detail
    result = await get_valuation_detail(code, _compute_percentile)
    return result.model_dump()


async def get_stock_technical_indicators(code: str) -> Any:
    from app.services.stock.kline import get_kline
    from app.services.technical.indicators import calculate_all
    kline_data = await get_kline(code)
    indicators = calculate_all(kline_data.items)
    indicators.pop("series", None)
    return indicators


async def get_stock_kline(code: str, period: str = "daily") -> Any:
    from app.services.stock.kline import get_kline
    result = await get_kline(code, period=period)
    return result.model_dump()


async def get_stock_financial(code: str, indicator: str = "balance") -> Any:
    from app.services.stock.financials import get_financial
    return await get_financial(code, indicator=indicator)


async def get_stock_news(code: str) -> Any:
    from app.services.analysis.news import get_stock_news as _get_stock_news
    result = await _get_stock_news(code)
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in result]


async def get_stock_sentiment(code: str) -> Any:
    from app.services.analysis.retail import get_stock_sentiment
    return await get_stock_sentiment(code)


async def screen_stocks(**kwargs) -> Any:
    from app.models.screener import ScreenerFilter
    from app.services.screener.screening import screen_stocks as _screen_stocks
    filter_data = {k: v for k, v in kwargs.items() if v is not None}
    if "page" not in filter_data:
        filter_data["page"] = 1
    if "page_size" not in filter_data:
        filter_data["page_size"] = 20
    sf = ScreenerFilter(**filter_data)
    result = await _screen_stocks(sf)
    return result.model_dump()


async def get_industries() -> Any:
    from app.services.screener.industry import get_industry_list
    return await get_industry_list()


def _get_iwencai_provider():
    from app.config import get_settings
    from app.services.providers.iwencai import iwencai_provider
    settings = get_settings()
    if not settings.iwencai_enabled:
        return None
    return iwencai_provider


async def iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    if channel == "news":
        result = await call_blocking(iwencai_provider.search_news, query, size)
        return [item.model_dump() for item in result[:size]]
    result = await call_blocking(iwencai_provider.search, query, channel, size)
    return iwencai_provider.dedup_articles(result)[:size]


async def iwencai_query(query: str, limit: int = 30) -> Any:
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await call_blocking(iwencai_provider.query_stock_data, query, 1, limit)


async def iwencai_select_stock(query: str, limit: int = 20) -> Any:
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await call_blocking(iwencai_provider.select_stocks, query, 1, limit)


async def iwencai_market_macro(query: str, limit: int = 20) -> Any:
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await call_blocking(iwencai_provider.query_market_macro, query, 1, limit)
