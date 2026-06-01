import asyncio
import logging
from app.services.providers.baidu import baidu_provider as _baidu_provider
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
    baidu_task = call_blocking(_baidu_provider.fetch_market_new)
    kr36_task = call_blocking(_rss_provider.fetch_36kr_news)
    xueqiu_task = call_blocking(_rss_provider.fetch_xueqiu_news)
    jiemain_task = call_blocking(_rss_provider.fetch_jiemain_news)
    eeo_task = call_blocking(_rss_provider.fetch_eeo_news)

    em_result, rss_result, news_cls_result, baidu_result, kr36_result, xueqiu_result, jiemain_result, eeo_result = await asyncio.gather(
        em_task, rss_task, news_cls_task, baidu_task, kr36_task, xueqiu_task, jiemain_task, eeo_task, return_exceptions=True
    )

    if isinstance(em_result, Exception):
        logger.warning(f"东方财富新闻获取失败: error={em_result}")
    else:
        result.extend(em_result[:20])

    if isinstance(rss_result, Exception):
        logger.warning(f"RSS新闻获取失败: error={rss_result}")
    else:
        result.extend(rss_result[:20])

    if isinstance(news_cls_result, Exception):
        logger.warning(f"财联社新闻获取失败: error={news_cls_result}")
    else:
        result.extend(news_cls_result[:20])

    if isinstance(baidu_result, Exception):
        logger.warning(f"百度新闻获取失败: error={baidu_result}")
    else:
        result.extend(baidu_result[:20])

    if isinstance(kr36_result, Exception):
        logger.warning(f"36氪新闻获取失败: error={kr36_result}")
    else:
        result.extend(kr36_result[:20])

    if isinstance(xueqiu_result, Exception):
        logger.warning(f"雪球新闻获取失败: error={xueqiu_result}")
    else:
        result.extend(xueqiu_result[:20])

    if isinstance(jiemain_result, Exception):
        logger.warning(f"界面新闻获取失败: error={jiemain_result}")
    else:
        result.extend(jiemain_result[:20])

    if isinstance(eeo_result, Exception):
        logger.warning(f"经济观察报获取失败: error={eeo_result}")
    else:
        result.extend(eeo_result[:20])

    result = filter_recent_news_items(result)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:20]

    cache.set(cache_key, result, ttl=600)
    return result


async def get_market_feed() -> list:
    cache_key = dated_cache_key("market_feed")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    em_task = call_blocking(_eastmoney_provider.fetch_market_news)
    em_fast_task = call_blocking(_eastmoney_provider.fetch_global_market_news)
    rss_task = call_blocking(_rss_provider.fetch_market_news)
    zaobao_task = call_blocking(_rss_provider.fetch_zaobao_news)
    news_cls_task = call_blocking(_cls_provider.fetch_market_news)
    baidu_task = call_blocking(_baidu_provider.fetch_market_new)
    kr36_task = call_blocking(_rss_provider.fetch_36kr_news)
    xueqiu_task = call_blocking(_rss_provider.fetch_xueqiu_news)
    jiemain_task = call_blocking(_rss_provider.fetch_jiemain_news)
    eeo_task = call_blocking(_rss_provider.fetch_eeo_news)

    em_result, em_fast_result, rss_result, zaobao_result, news_cls_result, baidu_result, kr36_result, xueqiu_result, jiemain_result, eeo_result = await asyncio.gather(
        em_task, em_fast_task, rss_task, zaobao_task, news_cls_task, baidu_task, kr36_task, xueqiu_task, jiemain_task, eeo_task, return_exceptions=True
    )

    if isinstance(em_result, Exception):
        logger.warning(f"东方财富新闻获取失败: error={em_result}")
    else:
        result.extend(em_result[:20])

    if isinstance(em_fast_result, Exception):
        logger.warning(f"东方财富快讯获取失败: error={em_fast_result}")
    else:
        result.extend(em_fast_result[:20])

    if isinstance(rss_result, Exception):
        logger.warning(f"RSS新闻获取失败: error={rss_result}")
    else:
        result.extend(rss_result[:20])

    if isinstance(zaobao_result, Exception):
        logger.warning(f"联合早报获取失败: error={zaobao_result}")
    else:
        result.extend(zaobao_result[:20])

    if isinstance(news_cls_result, Exception):
        logger.warning(f"财联社新闻获取失败: error={news_cls_result}")
    else:
        result.extend(news_cls_result[:20])

    if isinstance(baidu_result, Exception):
        logger.warning(f"百度新闻获取失败: error={baidu_result}")
    else:
        result.extend(baidu_result[:20])

    if isinstance(kr36_result, Exception):
        logger.warning(f"36氪新闻获取失败: error={kr36_result}")
    else:
        result.extend(kr36_result[:20])

    if isinstance(xueqiu_result, Exception):
        logger.warning(f"雪球新闻获取失败: error={xueqiu_result}")
    else:
        result.extend(xueqiu_result[:20])

    if isinstance(jiemain_result, Exception):
        logger.warning(f"界面新闻获取失败: error={jiemain_result}")
    else:
        result.extend(jiemain_result[:20])

    if isinstance(eeo_result, Exception):
        logger.warning(f"经济观察报获取失败: error={eeo_result}")
    else:
        result.extend(eeo_result[:20])

    result = filter_recent_news_items(result, days=1)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:300]

    cache.set(cache_key, result, ttl=120)
    return result
