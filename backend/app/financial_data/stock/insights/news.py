"""个股资讯服务。"""

import asyncio
import logging

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import cls_semaphore, eastmoney_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import is_hk_code, normalize_code
from app.core.news import dedupe_news_items, filter_recent_news_items, news_sort_key
from app.domain.news import CategorizedStockNews, NewsSearchItem
from app.financial_data.stock.profile.name_map import get_stock_name_map
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_news_singleflight: AsyncSingleFlight[list[NewsSearchItem]] = AsyncSingleFlight()
_categorized_news_singleflight: AsyncSingleFlight[CategorizedStockNews] = AsyncSingleFlight()


def _get_cls_provider():
    """延迟获取财联社 provider。"""
    return get_provider("cls")


def _get_eastmoney_provider():
    """延迟获取东方财富 provider。"""
    return get_provider("eastmoney")


async def _load_stock_news(sym) -> list[NewsSearchItem]:
    """Load and merge recent stock news from Eastmoney and CLS providers.

    Param:
        sym: normalized stock code formats (SymbolFormats)
    Return:
        list of up to 20 deduplicated, recent NewsSearchItem sorted by time descending
    """
    result = []
    stock_name = ""
    try:
        stock_name_map = await get_stock_name_map()
        stock_name = str(stock_name_map.get(sym.raw, "")).strip()
    except Exception as e:
        logger.info(f"股票名称映射获取失败: {sym.raw}, error={e}")

    em_task = provider_gateway.call_blocking(
        "eastmoney",
        "stock_news",
        _get_eastmoney_provider().fetch_stock_news,
        semaphore=eastmoney_semaphore,
        code=sym.raw,
        code_name=stock_name,
    )
    cls_task = provider_gateway.call_blocking(
        "cls",
        "stock_news",
        _get_cls_provider().fetch_market_news,
        semaphore=cls_semaphore,
        code=sym.raw,
        code_name=stock_name,
    )
    em_result, cls_result = await asyncio.gather(em_task, cls_task, return_exceptions=True)

    if isinstance(em_result, Exception):
        logger.warning(f"个股新闻获取失败: {sym.raw}, error={em_result}")
    else:
        result.extend(em_result[:10])

    if isinstance(cls_result, Exception):
        logger.warning(f"财联社电报获取失败: {sym.raw}, error={cls_result}")
    else:
        result.extend(cls_result)

    result = filter_recent_news_items(result)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    return result[:20]


async def _load_and_cache_stock_news(cache_key: str, sym) -> list[NewsSearchItem]:
    result = await _load_stock_news(sym)
    cache.set(cache_key, result, ttl=600)
    return result


async def get_stock_news(code: str) -> list[NewsSearchItem]:
    """Get the recent news items for a stock, using cache and single-flight deduplication.

    Param:
        code: 6-digit stock code or HK code
    Return:
        list of up to 20 NewsSearchItem sorted by publish time descending
    """
    if is_hk_code(code):
        from app.financial_data.hk.service import normalize_hk_code

        norm_code = normalize_hk_code(code)
        cache_key = dated_cache_key("news", norm_code)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        return []

    sym = normalize_code(code)
    cache_key = dated_cache_key("news", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    return await _news_singleflight.do(
        cache_key,
        lambda: _load_and_cache_stock_news(cache_key, sym),
    )


async def get_stock_news_categorized(code: str) -> CategorizedStockNews:
    """Get stock news split into Eastmoney and CLS categories with daily caching.

    Param:
        code: 6-digit stock code or HK code
    Return:
        dict with keys "code", "eastmoney_news", and "cls_news"
    """
    if is_hk_code(code):
        from app.financial_data.hk.service import normalize_hk_code

        norm_code = normalize_hk_code(code)
        return CategorizedStockNews(
            code=norm_code,
            eastmoney_news=[],
            cls_news=[],
        )

    sym = normalize_code(code)
    cache_key = dated_cache_key("news_categorized", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return CategorizedStockNews.model_validate(cached)

    async def load_and_cache() -> CategorizedStockNews:
        all_news = await get_stock_news(code)
        result = CategorizedStockNews(
            code=sym.raw,
            eastmoney_news=[item for item in all_news if str(item.source).strip() != "财联社"],
            cls_news=[item for item in all_news if str(item.source).strip() == "财联社"],
        )
        cache.set(cache_key, result, ttl=600)
        return result

    return await _categorized_news_singleflight.do(cache_key, load_and_cache)
