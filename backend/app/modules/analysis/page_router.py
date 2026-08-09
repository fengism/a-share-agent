"""分析页面聚合端点。"""

import asyncio
import logging

from fastapi import APIRouter, Depends

from app.configuration import get_effective_settings
from app.core.cache import cache_date, one_year_ago_date
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.market_data.stock.public import get_basic_info, get_intraday, get_kline, get_valuation
from app.modules.analysis.persistence.repository import get_latest_analysis
from app.modules.analysis.schemas import AnalysisPageData
from app.modules.auth.public import AuthenticatedUser, require_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analysis-page/{code}", response_model=AnalysisPageData)
async def get_analysis_page(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """聚合分析页面所需的所有数据，并发加载。

    将 stock/info、stock/kline、stock/intraday、stock/valuation、analysis/result
    合并为一个响应，减少前端页面加载时的 HTTP 往返次数。

    Param:
        code: 6 位股票代码
    Return:
        AnalysisPageData: 分析页面所需的全部数据
    """
    today = cache_date()
    year_ago = one_year_ago_date()

    results = await asyncio.gather(
        get_basic_info(code),
        get_kline(code, period="daily", start_date=year_ago, end_date=today),
        get_intraday(code),
        get_valuation(code),
        _safe_get_latest_analysis(
            code,
            user["id"],
            get_effective_settings().cache_ttl_analysis,
        ),
        return_exceptions=True,
    )

    def _unwrap(val, name: str):
        if isinstance(val, Exception):
            logger.warning(f"分析聚合页 {name} 加载失败: {val}")
            return None
        return val

    return AnalysisPageData(
        stock_info=_unwrap(results[0], "stock_info"),
        kline=_unwrap(results[1], "kline"),
        intraday=_unwrap(results[2], "intraday"),
        valuation=_unwrap(results[3], "valuation"),
        cached_analysis=_unwrap(results[4], "cached_analysis"),
    )


async def _safe_get_latest_analysis(code: str, user_id: int, cache_ttl: int):
    """安全获取最新分析结果，失败返回 None。

    Param:
        code: 6 位股票代码
    Return:
        最新分析结果 dict；读取失败返回 None
    """
    try:
        return await call_blocking(
            get_latest_analysis,
            code,
            user_id,
            cache_ttl=cache_ttl,
            semaphore=misc_semaphore,
        )
    except Exception:
        logger.warning(
            "分析聚合页缓存读取失败: code=%s user_id=%s",
            code,
            user_id,
            exc_info=True,
        )
        return None
