import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.news_utils import dedupe_news_items, filter_recent_news_items, news_sort_key
from app.utils.singleflight import AsyncSingleFlight

_news_singleflight: AsyncSingleFlight[list] = AsyncSingleFlight()

logger = logging.getLogger(__name__)

KUAIXUN_LABEL = "7×24 快讯"


@dataclass
class NewsSource:
    """A single news source to fetch in parallel."""
    name: str  # Chinese label for logging
    fetcher: Callable  # sync function to call via call_blocking
    limit: int = 20  # max items to take from this source


def _get_baidu_provider():
    """延迟获取百度 provider。"""
    return get_provider("baidu")


def _get_cls_provider():
    """延迟获取财联社 provider。"""
    return get_provider("cls")


def _get_eastmoney_provider():
    """延迟获取东方财富 provider。"""
    return get_provider("eastmoney")


def _get_news_provider():
    """延迟获取 News（RSS）provider。"""
    return get_provider("rss")


def _get_twitter_provider():
    """延迟获取 Twitter provider。"""
    return get_provider("twitter")


# ── 源列表构建函数（延迟绑定，保证 monkeypatch 生效） ────

def _kuaixun_sources() -> list[NewsSource]:
    """返回快讯数据源列表。"""
    eastmoney = _get_eastmoney_provider()
    baidu = _get_baidu_provider()
    rss = _get_news_provider()
    return [
        NewsSource("东方财富7×24快讯", eastmoney.fetch_market_kuaixun, limit=50),
        NewsSource("百度7×24快讯", baidu.fetch_market_kuaixun, limit=50),
        NewsSource("华尔街见闻7×24快讯", rss.fetch_market_kuaixun, limit=50),
    ]


def _news_sources() -> list[NewsSource]:
    """返回非快讯类新闻数据源列表。"""
    eastmoney = _get_eastmoney_provider()
    rss = _get_news_provider()
    cls = _get_cls_provider()
    return [
        NewsSource("东方财富财经新闻", eastmoney.fetch_market_news),
        NewsSource("中国财经新闻", rss.fetch_china_news),
        NewsSource("联合早报", rss.fetch_zaobao_news),
        NewsSource("财联社新闻", cls.fetch_market_news),
        NewsSource("36氪新闻", rss.fetch_36kr_news),
        NewsSource("雪球新闻", rss.fetch_xueqiu_news),
        NewsSource("界面新闻", rss.fetch_jiemain_news),
        NewsSource("经济观察报", rss.fetch_eeo_news),
        NewsSource("华尔街见闻", rss.fetch_wallstreetcn_news),
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

    使用 SingleFlight 防止缓存击穿，高并发时仅一次实际加载。

    Param:
        无
    Return:
        快讯条目列表，source 统一为 "7×24 快讯"，按发布时间倒序
    """
    cache_key = dated_cache_key("market_kuaixun")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    async def _load() -> list:
        result = await _gather_news(_kuaixun_sources())
        result = _unify_source(result, KUAIXUN_LABEL)
        result = filter_recent_news_items(result, days=1)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:200]
        cache.set(cache_key, result, ttl=60)
        return result

    return await _news_singleflight.do(cache_key, _load)


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

    async def _load() -> list:
        result = await _gather_news(_news_sources())
        result = filter_recent_news_items(result, days=1)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:100]
        cache.set(cache_key, result, ttl=300)
        return result

    return await _news_singleflight.do(cache_key, _load)


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

    async def _load() -> list:
        result = await _gather_news(_all_sources())
        result = filter_recent_news_items(result)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:30]
        cache.set(cache_key, result, ttl=600)
        return result

    return await _news_singleflight.do(cache_key, _load)


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

    async def _load() -> list:
        result = await _gather_news(_all_sources())
        result = filter_recent_news_items(result, days=1)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:300]
        cache.set(cache_key, result, ttl=120)
        return result

    return await _news_singleflight.do(cache_key, _load)


async def get_twitter_feed() -> list:
    """从数据库读取 Twitter/X 财经账号的最新推文和文章。

    数据由后台定期任务 `refresh_twitter_feed_task` 负责拉取写入，
    本函数仅查询数据库。

    Param:
        无
    Return:
        NewsSearchItem 列表，按发布时间倒序
    """
    from app.db.twitter_store import query_twitter_posts_by_authors

    feeds = _get_twitter_provider().twitter_feeds
    if not feeds:
        return []

    db_rows = query_twitter_posts_by_authors(feeds)
    if not db_rows:
        return []

    from app.models.search_item import NewsSearchItem
    return [NewsSearchItem(**row) for row in db_rows]

async def refresh_twitter_feed_now() -> dict:
    """立即强制刷新 Twitter 资讯数据库（不等待后台周期任务）。

    直接从 Twitter provider 拉取配置账号的最新推文并写入数据库。

    Return:
        包含刷新状态的字典 (status, authors, posts_count)
    """
    from app.config import get_settings
    from app.services.providers.twitter import twitter_provider
    from app.db.twitter_store import save_twitter_posts, get_stale_authors

    feeds = get_settings().twitter_feeds
    if not feeds:
        return {"status": "skipped", "reason": "未配置 Twitter feeds"}

    stale = await asyncio.to_thread(get_stale_authors, feeds)
    if not stale:
        return {"status": "skipped", "reason": "没有需要刷新的账号（5 分钟内已刷新过）"}

    logger.info(f"Twitter manual refresh: fetching stale authors: {stale}")
    raw = await asyncio.to_thread(twitter_provider.fetch_posts_for_users, stale)
    await asyncio.to_thread(save_twitter_posts, [p.model_dump() for p in raw])
    return {"status": "ok", "authors": stale, "posts_count": len(raw)}
