"""个股公告服务：巨潮资讯（法定披露）为主，新浪财经兜底。"""

import asyncio
import logging
from dataclasses import dataclass

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import cninfo_semaphore, sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import is_hk_code, normalize_code
from app.financial_data.stock.insights.schemas import StockBulletinItem, StockBulletinPage
from app.financial_data.stock.insights.sources import (
    CNINFO_ANNOUNCEMENT_QUERY_API,
    CNINFO_BULLETIN_SOURCE_ID,
    SINA_BULLETIN_LIST_API,
    SINA_BULLETIN_SOURCE_ID,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

BULLETIN_CACHE_TTL_SECONDS = 1800  # 公告更新频率低，单页缓存 30 分钟
BULLETIN_MAX_PAGE_SIZE = 30

_bulletin_singleflight: AsyncSingleFlight[StockBulletinPage] = AsyncSingleFlight()


@dataclass(frozen=True)
class _BulletinSource:
    provider: str
    operation: str
    method: str
    source_id: str
    source_api: str
    semaphore: asyncio.Semaphore


# 巨潮资讯是上市公司法定信息披露平台，权威且覆盖全，优先使用；
# 请求失败或返回空列表时回退新浪财经。
_BULLETIN_SOURCES = (
    _BulletinSource(
        provider="cninfo",
        operation="stock_bulletins",
        method="fetch_stock_bulletins",
        source_id=CNINFO_BULLETIN_SOURCE_ID,
        source_api=CNINFO_ANNOUNCEMENT_QUERY_API,
        semaphore=cninfo_semaphore,
    ),
    _BulletinSource(
        provider="sina",
        operation="stock_bulletins",
        method="fetch_stock_bulletins",
        source_id=SINA_BULLETIN_SOURCE_ID,
        source_api=SINA_BULLETIN_LIST_API,
        semaphore=sina_semaphore,
    ),
)


async def get_stock_bulletins(code: str, page: int = 1, page_size: int = 10) -> StockBulletinPage:
    """获取个股公告分页列表。

    Param:
        code: 6 位股票代码或港股代码
        page: 页码，从 1 开始
        page_size: 每页条数（1-30）
    Return:
        StockBulletinPage，含公告条目与总页数
    """
    page = max(1, page)
    page_size = min(max(1, page_size), BULLETIN_MAX_PAGE_SIZE)
    if is_hk_code(code):
        from app.financial_data.hk.service import normalize_hk_code

        norm_code = normalize_hk_code(code)
        return StockBulletinPage(code=norm_code, items=[], total=0, page=page, page_size=page_size)

    sym = normalize_code(code)
    cache_key = dated_cache_key("stock_bulletins", sym.raw, page, page_size)
    cached = cache.get(cache_key)
    if cached is not None:
        return StockBulletinPage.model_validate(cached)

    async def load_and_cache() -> StockBulletinPage:
        raw, source = await _fetch_bulletin_page(sym.raw, page, page_size)
        result = _build_bulletin_page(sym.raw, raw, page=page, page_size=page_size, source=source)
        cache.set(cache_key, result, ttl=BULLETIN_CACHE_TTL_SECONDS)
        return result

    return await _bulletin_singleflight.do(cache_key, load_and_cache)


async def _fetch_bulletin_page(code: str, page: int, page_size: int) -> tuple[dict, _BulletinSource]:
    last_error: Exception | None = None
    for index, source in enumerate(_BULLETIN_SOURCES):
        try:
            provider = get_provider(source.provider)
            raw = await provider_gateway.call_blocking(
                source.provider,
                source.operation,
                getattr(provider, source.method),
                code,
                page=page,
                page_size=page_size,
                semaphore=source.semaphore,
                is_fallback_attempt=index > 0,
            )
            if not raw.get("items"):
                raise ValueError(f"{source.provider} 公告列表为空")
            return raw, source
        except Exception as error:
            last_error = error
            logger.info(
                "公告数据源失败: provider=%s code=%s error=%s",
                source.provider,
                code,
                error,
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError("公告数据源为空")


def _build_bulletin_page(
    code: str,
    raw: dict,
    *,
    page: int,
    page_size: int,
    source: _BulletinSource,
) -> StockBulletinPage:
    items = [
        StockBulletinItem.model_validate(entry).model_copy(
            update={"source": source.source_id, "source_api": source.source_api}
        )
        for entry in raw.get("items", [])
    ]
    return StockBulletinPage(
        code=code,
        name=str(raw.get("name") or ""),
        page=page,
        page_size=page_size,
        total_pages=int(raw.get("total_pages") or 0),
        source=source.source_id,
        items=items,
    )
