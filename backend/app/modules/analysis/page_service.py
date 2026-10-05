"""分析页面聚合数据的应用服务。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.market import is_hk_code
from app.domain.market import KlineData
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, completed_market_date
from app.financial_data.stock.public import (
    IntradayData,
    StockBasicInfo,
    StockValuation,
    get_basic_info,
    get_intraday,
    get_kline,
    get_valuation,
)
from app.financial_data.stock.quotes.chip_distribution import calculate_chip_distribution
from app.financial_data.stock.quotes.key_levels import calculate_key_levels
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence.repository import get_latest_analysis
from app.modules.analysis.schemas import AnalysisKeyLevels, AnalysisPageData, AnalysisPageSection

logger = logging.getLogger(__name__)

_SECTION_TIMEOUT_CAPS = {
    "stock_info": 6.0,
    "kline": 15.0,
    "intraday": 5.0,
    "valuation": 10.0,
    "cached_analysis": 2.0,
}


def _year_before(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def _default_kline_date_range(now: datetime | None = None) -> tuple[str, str]:
    """Use only completed daily bars; intraday data represents the active session."""
    local_now = now or datetime.now(SHANGHAI_TIMEZONE)
    end_date = completed_market_date(
        local_now.date(),
        now=local_now,
        trading_dates=None,
    )
    return _year_before(end_date).strftime("%Y%m%d"), end_date.strftime("%Y%m%d")

@dataclass(frozen=True)
class AnalysisPageLoaders:
    """聚合服务依赖的数据加载端口。"""

    stock_info: Callable[[str], Awaitable[StockBasicInfo]]
    kline: Callable[..., Awaitable[KlineData]]
    intraday: Callable[[str], Awaitable[IntradayData]]
    valuation: Callable[[str], Awaitable[StockValuation]]
    cached_analysis: Callable[[str, int, int], Awaitable[AnalysisResult | None]]


async def _load_hk_stock_info(code: str) -> StockBasicInfo:
    """港股基础资料：只映射行情能证明的字段，其余保持 None。

    A 股口径的 get_basic_info 对港股无效（行业分类、上市日期、概念板块都没有
    可靠来源），因此这里不做任何跨市场口径映射。
    """
    from app.financial_data.hk.analysis_support import get_hk_stock_profile

    profile = await get_hk_stock_profile(code)
    quote = profile.get("quote") or {}
    return StockBasicInfo(
        code=str(quote.get("code") or code),
        name=str(quote.get("name") or code),
        current_price=quote.get("price"),
    )


async def _load_stock_info(code: str) -> StockBasicInfo:
    if is_hk_code(code):
        return await _load_hk_stock_info(code)
    return await get_basic_info(code)


async def _load_cached_analysis(code: str, user_id: int, cache_ttl: int) -> AnalysisResult | None:
    return await call_blocking(
        get_latest_analysis,
        code,
        user_id,
        cache_ttl=cache_ttl,
        semaphore=misc_semaphore,
    )


DEFAULT_ANALYSIS_PAGE_LOADERS = AnalysisPageLoaders(
    stock_info=_load_stock_info,
    kline=get_kline,
    intraday=get_intraday,
    valuation=get_valuation,
    cached_analysis=_load_cached_analysis,
)


async def get_analysis_page_data(
    code: str,
    *,
    user_id: int,
    cache_ttl: int,
    section_timeout_seconds: float,
    loaders: AnalysisPageLoaders | None = None,
    date_range: tuple[str, str] | None = None,
    include_market_data: bool = True,
) -> AnalysisPageData:
    """并发聚合分析页面数据，并显式标记不可用分区。"""
    active_loaders = loaders or DEFAULT_ANALYSIS_PAGE_LOADERS
    if not include_market_data:
        # The research UI reuses the stock page's query cache for market data.
        try:
            cached = await asyncio.wait_for(
                active_loaders.cached_analysis(code, user_id, cache_ttl),
                timeout=min(section_timeout_seconds, _SECTION_TIMEOUT_CAPS["cached_analysis"]),
            )
            return AnalysisPageData(cached_analysis=cached)
        except Exception as exc:
            logger.warning("分析页历史分析加载失败: %s", exc)
            return AnalysisPageData(partial=True, unavailable_sections=["cached_analysis"])
    start_date, end_date = date_range or _default_kline_date_range()
    requests: list[tuple[AnalysisPageSection, Awaitable[Any]]] = [
        ("stock_info", active_loaders.stock_info(code)),
        (
            "kline",
            active_loaders.kline(
                code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
            ),
        ),
        ("intraday", active_loaders.intraday(code)),
        ("cached_analysis", active_loaders.cached_analysis(code, user_id, cache_ttl)),
    ]
    # 港股没有 A 股口径的估值接口：与其建好协程再等它超时降级，不如根本不发起，
    # 由下面的 unavailable_sections 明确说明这一项对港股不适用。
    if not is_hk_code(code):
        requests.insert(3, ("valuation", active_loaders.valuation(code)))
    results = await asyncio.gather(
        *(
            asyncio.wait_for(
                request,
                timeout=min(section_timeout_seconds, _SECTION_TIMEOUT_CAPS[section]),
            )
            for section, request in requests
        ),
        return_exceptions=True,
    )

    values: dict[AnalysisPageSection, Any] = {
        "stock_info": None,
        "kline": None,
        "intraday": None,
        "valuation": None,
        "cached_analysis": None,
    }
    unavailable_sections: list[AnalysisPageSection] = (
        ["valuation"] if is_hk_code(code) else []
    )
    for (section, _), result in zip(requests, results, strict=True):
        if isinstance(result, TimeoutError):
            effective_timeout = min(section_timeout_seconds, _SECTION_TIMEOUT_CAPS[section])
            logger.warning("分析聚合页 %s 加载超时: timeout=%ss", section, effective_timeout)
            values[section] = None
            unavailable_sections.append(section)
        elif isinstance(result, Exception):
            logger.warning("分析聚合页 %s 加载失败: %s", section, result)
            values[section] = None
            unavailable_sections.append(section)
        else:
            values[section] = result

    kline: KlineData | None = values["kline"]
    key_levels = None
    chip_distribution = None
    if kline is not None:
        levels = calculate_key_levels(kline.items)
        key_levels = AnalysisKeyLevels(
            current_price=levels.current_price,
            support=levels.support,
            resistance=levels.resistance,
        )
        try:
            chip_distribution = calculate_chip_distribution(kline.items, code=kline.code)
        except (ValueError, RuntimeError) as exc:
            logger.warning("分析聚合页筹码分布计算失败: code=%s error=%s", code, exc)

    return AnalysisPageData(
        stock_info=values["stock_info"],
        kline=kline,
        intraday=values["intraday"],
        valuation=values["valuation"],
        cached_analysis=values["cached_analysis"],
        key_levels=key_levels,
        chip_distribution=chip_distribution,
        partial=bool(unavailable_sections),
        unavailable_sections=unavailable_sections,
    )
