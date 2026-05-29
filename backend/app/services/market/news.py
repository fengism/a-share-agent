import asyncio
import logging
from app.services.providers.cls import cls_provider as _cls_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.rss import rss_provider as _rss_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.news_utils import dedupe_news_items, filter_recent_news_items, news_sort_key

logger = logging.getLogger(__name__)



async def get_market_news() -> list:
    cache_key = dated_cache_key("market_news")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    em_task = call_blocking(_eastmoney_provider.fetch_market_news)
    rss_task = call_blocking(_rss_provider.fetch_market_news)
    news_cls_task = call_blocking(_cls_provider.fetch_market_news)

    em_result, rss_result, news_cls_result = await asyncio.gather(
        em_task, rss_task, news_cls_task, return_exceptions=True
    )

    if isinstance(em_result, Exception):
        logger.warning(f"东方财富新闻获取失败: error={em_result}")
    else:
        result.extend(em_result[:10])

    if isinstance(rss_result, Exception):
        logger.warning(f"RSS新闻获取失败: error={rss_result}")
    else:
        result.extend(rss_result)

    if isinstance(news_cls_result, Exception):
        logger.warning(f"财联社新闻获取失败: error={news_cls_result}")
    else:
        result.extend(news_cls_result)

    result = filter_recent_news_items(result)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:20]

    cache.set(cache_key, result, ttl=600)
    return result
