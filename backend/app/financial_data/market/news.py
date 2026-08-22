import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.news import dedupe_news_items, filter_recent_news_items, news_sort_key
from app.domain.news import NewsSearchItem
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_news_singleflight: AsyncSingleFlight[list[NewsSearchItem]] = AsyncSingleFlight()
_news_semaphore = asyncio.Semaphore(4)  # 限制同时拉取的数据源数量

logger = logging.getLogger(__name__)

KUAIXUN_LABEL = "7×24 快讯"


@dataclass
class NewsSource:
    """A single news source to fetch in parallel."""
    name: str  # Chinese label for logging
    fetcher: Callable  # sync function to call via call_blocking
    limit: int = 20  # max items to take from this source
    api: str = ""


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


# ── 源列表构建函数（延迟绑定，保证 monkeypatch 生效） ────

def _kuaixun_sources() -> list[NewsSource]:
    """返回快讯数据源列表。"""
    eastmoney = _get_eastmoney_provider()
    baidu = _get_baidu_provider()
    rss = _get_news_provider()
    return [
        NewsSource(
            "东方财富7×24快讯",
            eastmoney.fetch_market_kuaixun,
            limit=50,
            api="https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
        ),
        NewsSource(
            "百度7×24快讯",
            baidu.fetch_market_kuaixun,
            limit=50,
            api="https://finance.pae.baidu.com/selfselect/expressnews",
        ),
        NewsSource(
            "华尔街见闻7×24快讯",
            rss.fetch_market_kuaixun,
            limit=50,
            api="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        ),
    ]


def _news_sources() -> list[NewsSource]:
    """返回非快讯类新闻数据源列表。"""
    eastmoney = _get_eastmoney_provider()
    rss = _get_news_provider()
    cls = _get_cls_provider()
    return [
        NewsSource("东方财富财经新闻", eastmoney.fetch_market_news, api="https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"),
        NewsSource("中国财经新闻", rss.fetch_china_news, api="https://www.chinanews.com/rss/finance.xml"),
        NewsSource("联合早报", rss.fetch_zaobao_news, api="https://plink.anyfeeder.com/zaobao/realtime/world"),
        NewsSource("财联社新闻", cls.fetch_market_news, api="https://www.cls.cn/v3/depth/home/assembled/1000"),
        NewsSource("36氪新闻", rss.fetch_36kr_news, api="https://36kr.com/feed"),
        NewsSource("雪球新闻", rss.fetch_xueqiu_news, api="https://plink.anyfeeder.com/weixin/xueqiujinghua"),
        NewsSource("界面新闻", rss.fetch_jiemain_news, api="https://plink.anyfeeder.com/jiemian/finance"),
        NewsSource("经济观察报", rss.fetch_eeo_news, api="https://plink.anyfeeder.com/weixin/eeo-com-cn"),
        NewsSource("华尔街见闻", rss.fetch_wallstreetcn_news, api="https://api-one-wscn.awtmt.com/apiv1/content/articles/hot"),
    ]


async def _gather_news(sources: list[NewsSource]) -> list[NewsSearchItem]:
    """Run all source tasks in parallel, collect results with error handling."""
    tasks = [
        provider_gateway.call_blocking(
            source.name,
            "market_news",
            source.fetcher,
            semaphore=_news_semaphore,
        )
        for source in sources
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    collected: list[NewsSearchItem] = []
    for source, result in zip(sources, results, strict=True):
        if isinstance(result, Exception):
            logger.warning(f"{source.name}获取失败: error={result}")
        else:
            collected.extend(
                NewsSearchItem.model_validate(item).model_copy(
                    update={"source_api": source.api},
                )
                for item in result[:source.limit]
            )
    return collected


def _mark_category(items: list[NewsSearchItem], category: str) -> list[NewsSearchItem]:
    return [item.model_copy(update={"category": category}) for item in items]


async def _compose_source_feeds() -> list[NewsSearchItem]:
    kuaixun, other_news = await asyncio.gather(
        get_market_kuaixun(),
        get_market_other_news(),
    )
    return [*kuaixun, *other_news]


async def get_market_kuaixun() -> list[NewsSearchItem]:
    """聚合多渠道 7×24 快讯，合并去重后返回。

    使用 SingleFlight 防止缓存击穿，高并发时仅一次实际加载。

    Param:
        无
    Return:
        保留真实来源并标记 category 的快讯条目列表
    """
    cache_key = dated_cache_key("market_kuaixun")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    async def _load() -> list[NewsSearchItem]:
        result = await _gather_news(_kuaixun_sources())
        result = _mark_category(result, KUAIXUN_LABEL)
        result = filter_recent_news_items(result, days=1)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:200]
        cache.set(cache_key, result, ttl=60)
        return result

    return await _news_singleflight.do(cache_key, _load)


async def get_market_other_news() -> list[NewsSearchItem]:
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

    async def _load() -> list[NewsSearchItem]:
        result = await _gather_news(_news_sources())
        result = _mark_category(result, "新闻")
        result = filter_recent_news_items(result, days=1)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:100]
        cache.set(cache_key, result, ttl=300)
        return result

    return await _news_singleflight.do(cache_key, _load)


async def get_market_news() -> list[NewsSearchItem]:
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

    async def _load() -> list[NewsSearchItem]:
        result = await _compose_source_feeds()
        result = filter_recent_news_items(result)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:30]
        cache.set(cache_key, result, ttl=600)
        return result

    return await _news_singleflight.do(cache_key, _load)


async def get_market_feed() -> list[NewsSearchItem]:
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

    async def _load() -> list[NewsSearchItem]:
        result = await _compose_source_feeds()
        result = filter_recent_news_items(result, days=1)
        result = dedupe_news_items(result)
        result.sort(key=news_sort_key, reverse=True)
        result = result[:300]
        cache.set(cache_key, result, ttl=120)
        return result

    return await _news_singleflight.do(cache_key, _load)
