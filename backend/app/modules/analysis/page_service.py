"""分析页面聚合数据的应用服务。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
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
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence.repository import get_latest_analysis
from app.modules.analysis.schemas import AnalysisPageData, AnalysisPageSection

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


async def _load_cached_analysis(code: str, user_id: int, cache_ttl: int) -> AnalysisResult | None:
    return await call_blocking(
        get_latest_analysis,
        code,
        user_id,
        cache_ttl=cache_ttl,
        semaphore=misc_semaphore,
    )


DEFAULT_ANALYSIS_PAGE_LOADERS = AnalysisPageLoaders(
    stock_info=get_basic_info,
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
) -> AnalysisPageData:
    """并发聚合分析页面数据，并显式标记不可用分区。"""
    active_loaders = loaders or DEFAULT_ANALYSIS_PAGE_LOADERS
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
        ("valuation", active_loaders.valuation(code)),
        ("cached_analysis", active_loaders.cached_analysis(code, user_id, cache_ttl)),
    ]
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

    values: dict[AnalysisPageSection, Any] = {}
    unavailable_sections: list[AnalysisPageSection] = []
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

    return AnalysisPageData(
        stock_info=values["stock_info"],
        kline=values["kline"],
        intraday=values["intraday"],
        valuation=values["valuation"],
        cached_analysis=values["cached_analysis"],
        partial=bool(unavailable_sections),
        unavailable_sections=unavailable_sections,
    )
