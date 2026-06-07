import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

from app.services.providers.baidu import baidu_provider as _baidu_provider
from app.services.providers.cls import cls_provider as _cls_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.rss import rss_provider as _rss_provider
from app.services.providers.twitter import twitter_provider as _twitter_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.news_utils import dedupe_news_items, filter_recent_news_items, news_sort_key

logger = logging.getLogger(__name__)

KUAIXUN_LABEL = "7×24 快讯"


@dataclass
class NewsSource:
    """A single news source to fetch in parallel."""
    name: str  # Chinese label for logging
    fetcher: Callable  # sync function to call via call_blocking
    limit: int = 20  # max items to take from this source


# ── 源列表构建函数（延迟绑定，保证 monkeypatch 生效） ────

def _kuaixun_sources() -> list[NewsSource]:
    """返回快讯数据源列表。"""
    return [
        NewsSource("东方财富7×24快讯", _eastmoney_provider.fetch_market_kuaixun, limit=50),
        NewsSource("百度7×24快讯", _baidu_provider.fetch_market_kuaixun, limit=50),
        NewsSource("华尔街见闻7×24快讯", _rss_provider.fetch_market_kuaixun, limit=50),
    ]


def _news_sources() -> list[NewsSource]:
    """返回非快讯类新闻数据源列表。"""
    return [
        NewsSource("东方财富财经新闻", _eastmoney_provider.fetch_market_news),
        NewsSource("中国财经新闻", _rss_provider.fetch_china_news),
        NewsSource("联合早报", _rss_provider.fetch_zaobao_news),
        NewsSource("财联社新闻", _cls_provider.fetch_market_news),
        NewsSource("36氪新闻", _rss_provider.fetch_36kr_news),
        NewsSource("雪球新闻", _rss_provider.fetch_xueqiu_news),
        NewsSource("界面新闻", _rss_provider.fetch_jiemain_news),
        NewsSource("经济观察报", _rss_provider.fetch_eeo_news),
        NewsSource("Twitter", _twitter_provider.fetch_market_news),
    ]


def _all_sources() -> list[NewsSource]:
    """返回全部数据源列表（快讯 + 新闻），用于 get_market_news / get_market_feed。"""
    return _kuaixun_sources() + _news_sources()


async def _gather_news(sources: list[NewsSource]) -> list:
    """Run all source tasks in parallel, collect results with error handling."""
    tasks = [call_blocking(s.fetcher) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    collected = []
    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.warning(f"{source.name}获取失败: error={result}")
        else:
            collected.extend(result[:source.limit])
    return collected


def _unify_source(items: list, label: str) -> list:
    """将列表中所有条目的 source 字段统一为指定标签。"""
    for item in items:
        item.source = label
    return items


async def get_market_kuaixun() -> list:
    """聚合多渠道 7×24 快讯，合并去重后返回。

    Param:
        无
    Return:
        快讯条目列表，source 统一为 "7×24 快讯"，按发布时间倒序
    """
    cache_key = dated_cache_key("market_kuaixun")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = await _gather_news(_kuaixun_sources())
    result = _unify_source(result, KUAIXUN_LABEL)
    result = filter_recent_news_items(result, days=1)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:200]

    cache.set(cache_key, result, ttl=60)
    return result


async def get_market_other_news() -> list:
    """聚合多渠道新闻（非快讯），去重后返回。

    Param:
        无
    Return:
        新闻条目列表，按发布时间倒序
    """
    cache_key = dated_cache_key("market_other_news")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = await _gather_news(_news_sources())
    result = filter_recent_news_items(result, days=1)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:100]

    cache.set(cache_key, result, ttl=300)
    return result


async def get_market_news() -> list:
    """聚合多渠道市场新闻列表，去重排序后取前 20 条。

    Param:
        无
    Return:
        新闻条目列表，按发布时间倒序排列
    """
    cache_key = dated_cache_key("market_news")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = await _gather_news(_all_sources())

    result = filter_recent_news_items(result)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:30]

    cache.set(cache_key, result, ttl=600)
    return result


async def get_market_feed() -> list:
    """聚合多渠道市场资讯流，去重后取最近一日的前 300 条。

    Param:
        无
    Return:
        新闻条目列表，按发布时间倒序排列
    """
    cache_key = dated_cache_key("market_feed")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = await _gather_news(_all_sources())

    result = filter_recent_news_items(result, days=1)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    result = result[:300]

    cache.set(cache_key, result, ttl=120)
    return result
