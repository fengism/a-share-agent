import asyncio
import logging

from app.models.search_item import NewsSearchItem
from app.services.providers import get_provider
from app.services.stock.name_map import get_stock_name_map
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking, cls_semaphore, eastmoney_semaphore
from app.utils.symbol_utils import normalize_code
from app.utils.news_utils import dedupe_news_items, filter_recent_news_items, news_sort_key

logger = logging.getLogger(__name__)

_news_inflight: dict[str, asyncio.Task[list[NewsSearchItem]]] = {}
_news_inflight_lock = asyncio.Lock()


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

    em_task = call_blocking(_get_eastmoney_provider().fetch_stock_news, semaphore=eastmoney_semaphore, code=sym.raw, code_name=stock_name)
    cls_task = call_blocking(_get_cls_provider().fetch_market_news, semaphore=cls_semaphore, code=sym.raw, code_name=stock_name)
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


async def _get_or_create_news_task(cache_key: str, sym):
    """Get cached news value or create/return a single-flight task to load it.

    Param:
        cache_key: dated cache key for the news
        sym: normalized stock code formats
    Return:
        tuple of (news loading task or None, cached value or None)
    """
    async with _news_inflight_lock:
        cached = cache.get(cache_key)
        if cached is not None:
            return None, cached

        task = _news_inflight.get(cache_key)
        if task is None:
            task = asyncio.create_task(_load_stock_news(sym))
            _news_inflight[cache_key] = task
        return task, None


async def get_stock_news(code: str) -> list[NewsSearchItem]:
    """Get the recent news items for a stock, using cache and single-flight deduplication.

    Param:
        code: 6-digit stock code
    Return:
        list of up to 20 NewsSearchItem sorted by publish time descending
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("news", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    task, cached = await _get_or_create_news_task(cache_key, sym)
    if cached is not None:
        return cached
    if task is None:
        return []

    try:
        result = await task
        cache.set(cache_key, result, ttl=600)
        return result
    finally:
        if task.done():
            async with _news_inflight_lock:
                if _news_inflight.get(cache_key) is task:
                    _news_inflight.pop(cache_key, None)


async def get_stock_news_categorized(code: str) -> dict:
    """Get stock news split into Eastmoney and CLS categories with daily caching.

    Param:
        code: 6-digit stock code
    Return:
        dict with keys "code", "eastmoney_news", and "cls_news"
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("news_categorized", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    all_news = await get_stock_news(code)
    eastmoney_news = [item for item in all_news if str(item.source).strip() != "财联社"]
    cls_news = [item for item in all_news if str(item.source).strip() == "财联社"]
    result = {
        "code": sym.raw,
        "eastmoney_news": eastmoney_news,
        "cls_news": cls_news,
    }
    cache.set(cache_key, result, ttl=600)
    return result
