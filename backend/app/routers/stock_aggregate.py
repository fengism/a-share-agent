"""聚合端点：集中返回分析页面所需的全部数据，减少前端并发请求数。"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.stock import StockBasicInfo, KlineData, IntradayData
from app.models.analysis import AnalysisResult
from app.services.stock.basic_info import get_basic_info
from app.services.stock.kline import get_kline
from app.services.stock.intraday import get_intraday
from app.services.stock.valuation import get_valuation
from app.services.analysis.storage import get_latest_analysis

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalysisPageData(BaseModel):
    """分析页面加载所需的聚合数据。"""
    stock_info: StockBasicInfo | None = None
    kline: KlineData | None = None
    intraday: IntradayData | None = None
    valuation: dict | None = None
    cached_analysis: AnalysisResult | None = None


@router.get("/analysis-page/{code}", response_model=AnalysisPageData)
async def get_analysis_page(code: str):
    """聚合分析页面所需的所有数据，并发加载。

    将 stock/info、stock/kline、stock/intraday、stock/valuation、analysis/result
    合并为一个响应，减少前端页面加载时的 HTTP 往返次数。

    Param:
        code: 6 位股票代码
    Return:
        AnalysisPageData: 分析页面所需的全部数据
    """
    from app.utils.cache import cache_date, one_year_ago_date

    today = cache_date()
    year_ago = one_year_ago_date()

    results = await asyncio.gather(
        get_basic_info(code),
        get_kline(code, period="daily", start_date=year_ago, end_date=today),
        get_intraday(code),
        get_valuation(code),
        _safe_get_latest_analysis(code),
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


async def _safe_get_latest_analysis(code: str):
    """安全获取最新分析结果，失败返回 None。"""
    try:
        return get_latest_analysis(code)
    except Exception:
        return None
