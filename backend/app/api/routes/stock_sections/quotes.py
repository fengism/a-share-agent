"""个股行情 HTTP API。"""

from fastapi import APIRouter, Query

from app.domain.market import KlineData
from app.financial_data.stock.public import ChipDistribution, IntradayData, TechnicalIndicators
from app.financial_data.stock.public import get_chip_distribution as get_chip_distribution_service
from app.financial_data.stock.public import get_intraday as get_intraday_service
from app.financial_data.stock.public import get_kline as get_stock_kline_service
from app.financial_data.stock.public import get_technical_indicators as get_technical_indicators_service

router = APIRouter()


def _normalize_adjust(adjust: str) -> str:
    """归一化复权参数：'none' 与 '' 均视作不复权。"""
    return "" if adjust == "none" else adjust


@router.get("/{code}/kline", response_model=KlineData)
async def get_kline(
    code: str,
    period: str = Query("daily", pattern="^(daily|weekly|monthly|annual)$"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    adjust: str = Query("qfq", pattern="^(qfq|hfq|none|)$"),
):
    """获取个股 K 线数据。"""
    return await get_stock_kline_service(
        code, period, start_date, end_date, _normalize_adjust(adjust)
    )


@router.get("/{code}/intraday", response_model=IntradayData)
async def get_intraday(code: str):
    """获取个股分时数据。"""
    return await get_intraday_service(code)


@router.get("/{code}/indicators", response_model=TechnicalIndicators)
async def get_indicators(
    code: str,
    period: str = Query("daily", pattern="^(daily|weekly|monthly|annual)$"),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """基于指定周期与日期范围的 K 线计算个股常用技术指标。"""
    return await get_technical_indicators_service(
        code,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{code}/chip-distribution", response_model=ChipDistribution)
async def get_chip_distribution(
    code: str,
    grid_size: int = Query(300, ge=100, le=1000),
    decay: float = Query(1.0, ge=0.1, le=3.0),
):
    """基于前复权日 K 与换手率在本地计算个股筹码分布。"""
    return await get_chip_distribution_service(code, grid_size=grid_size, decay=decay)
