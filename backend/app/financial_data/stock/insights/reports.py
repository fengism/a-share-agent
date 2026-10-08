"""个股研报评级服务（新浪 ReportService.getList，聚合最近 N 个月）。"""

import logging
from datetime import timedelta

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import is_hk_code, market_today, normalize_code
from app.financial_data.stock.insights.schemas import StockReportItem, StockReportPage
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

DEFAULT_REPORT_MONTHS = 6
REPORT_MAX_MONTHS = 24
REPORT_PAGE_SIZE = 30  # 单次抓取条数
REPORT_MAX_PAGES = 3  # 最多聚合页数，3 页 × 30 条足以覆盖半年
REPORT_CACHE_TTL_SECONDS = 1800  # 研报更新频率低，缓存 30 分钟

_report_singleflight: AsyncSingleFlight[StockReportPage] = AsyncSingleFlight()


def _get_sina_provider():
    """延迟获取新浪 provider。"""
    return get_provider("sina")


async def get_stock_reports(code: str, months: int = DEFAULT_REPORT_MONTHS) -> StockReportPage:
    """获取个股最近 N 个月的研报评级列表（按日期降序）。

    Param:
        code: 6 位股票代码或 5 位港股代码
        months: 回溯月数（1-24），默认 6 个月
    Return:
        StockReportPage，含过滤后的研报条目与总数
    """
    if is_hk_code(code):
        from app.financial_data.hk.service import normalize_hk_code

        return StockReportPage(
            code=normalize_hk_code(code),
            months=months,
            total_count=0,
            items=[],
        )

    sym = normalize_code(code)
    months = min(max(1, months), REPORT_MAX_MONTHS)
    cache_key = dated_cache_key("stock_reports", sym.raw, months)
    cached = cache.get(cache_key)
    if cached is not None:
        return StockReportPage.model_validate(cached)

    async def load_and_cache() -> StockReportPage:
        result = await _load_recent_reports(sym.raw, months)
        cache.set(cache_key, result, ttl=REPORT_CACHE_TTL_SECONDS)
        return result

    return await _report_singleflight.do(cache_key, load_and_cache)


async def _load_recent_reports(code: str, months: int) -> StockReportPage:
    """逐页抓取研报并过滤出最近 N 个月内的条目。

    接口按日期降序返回，遇到早于截止日期的整页即停止翻页。
    """
    cutoff = (market_today() - timedelta(days=30 * months)).isoformat()
    items: list[StockReportItem] = []
    seen_ids: set[str] = set()
    for page in range(1, REPORT_MAX_PAGES + 1):
        raw = await _fetch_report_page(code, page, REPORT_PAGE_SIZE)
        page_items = raw.get("items", [])
        if not page_items:
            break
        for entry in page_items:
            if str(entry.get("date") or "") >= cutoff:
                item = StockReportItem.model_validate(entry)
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        if str(page_items[-1].get("date") or "") < cutoff:
            break
    return StockReportPage(code=code, months=months, total_count=len(items), items=items)


async def _fetch_report_page(code: str, page: int, page_size: int) -> dict:
    provider = _get_sina_provider()
    return await provider_gateway.call_blocking(
        "sina",
        "stock_reports",
        provider.fetch_stock_reports,
        semaphore=sina_semaphore,
        code=code,
        page=page,
        page_size=page_size,
    )
