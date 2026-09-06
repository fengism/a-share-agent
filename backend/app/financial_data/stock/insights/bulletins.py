"""个股公告服务（新浪 CB_AllService.getBulletinList）。"""

import logging

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import normalize_code
from app.financial_data.stock.insights.schemas import StockBulletinItem, StockBulletinPage
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

BULLETIN_CACHE_TTL_SECONDS = 1800  # 公告更新频率低，单页缓存 30 分钟
BULLETIN_MAX_PAGE_SIZE = 30

_bulletin_singleflight: AsyncSingleFlight[StockBulletinPage] = AsyncSingleFlight()


def _get_sina_provider():
    """延迟获取新浪 provider。"""
    return get_provider("sina")


async def get_stock_bulletins(code: str, page: int = 1, page_size: int = 10) -> StockBulletinPage:
    """获取个股公告分页列表。

    Param:
        code: 6 位股票代码
        page: 页码，从 1 开始
        page_size: 每页条数（1-30）
    Return:
        StockBulletinPage，含公告条目与总页数
    """
    sym = normalize_code(code)
    page = max(1, page)
    page_size = min(max(1, page_size), BULLETIN_MAX_PAGE_SIZE)
    cache_key = dated_cache_key("stock_bulletins", sym.raw, page, page_size)
    cached = cache.get(cache_key)
    if cached is not None:
        return StockBulletinPage.model_validate(cached)

    async def load_and_cache() -> StockBulletinPage:
        raw = await _fetch_bulletin_page(sym.raw, page, page_size)
        result = _build_bulletin_page(sym.raw, raw, page=page, page_size=page_size)
        cache.set(cache_key, result, ttl=BULLETIN_CACHE_TTL_SECONDS)
        return result

    return await _bulletin_singleflight.do(cache_key, load_and_cache)


async def _fetch_bulletin_page(code: str, page: int, page_size: int) -> dict:
    provider = _get_sina_provider()
    return await provider_gateway.call_blocking(
        "sina",
        "stock_bulletins",
        provider.fetch_stock_bulletins,
        semaphore=sina_semaphore,
        code=code,
        page=page,
        page_size=page_size,
    )


def _build_bulletin_page(code: str, raw: dict, *, page: int, page_size: int) -> StockBulletinPage:
    items = [StockBulletinItem.model_validate(entry) for entry in raw.get("items", [])]
    return StockBulletinPage(
        code=code,
        name=str(raw.get("name") or ""),
        page=page,
        page_size=page_size,
        total_pages=int(raw.get("total_pages") or 0),
        items=items,
    )
