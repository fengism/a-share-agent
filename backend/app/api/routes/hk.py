from __future__ import annotations

from fastapi import APIRouter, Query

from app.domain.market import KlineData, MarketIndices
from app.financial_data.hk.schemas import (
    HKStockQuotePage,
    HKStockSearchResult,
    HKStockValuation,
)
from app.financial_data.hk.service import hk_market_service
from app.financial_data.stock.public import get_technical_indicators as get_technical_indicators_service
from app.financial_data.stock.quotes.indicators import TechnicalIndicators
from app.financial_data.stock.quotes.intraday import get_intraday
from app.financial_data.stock.quotes.schemas import IntradayData

router = APIRouter()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get("/stocks/realtime", response_model=HKStockQuotePage)
async def get_hk_stock_quotes(
    codes: str = Query("", description="逗号分隔的港股代码，例如 00700,09988"),
    query: str = Query("", max_length=80, description="按代码、中文名或英文名搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """获取新浪港股实时行情，并支持本地搜索和分页。"""
    return await hk_market_service.get_stock_quotes(
        codes=_split_csv(codes),
        query=query,
        page=page,
        page_size=page_size,
    )


@router.get("/stocks/search", response_model=HKStockSearchResult)
async def search_hk_stocks(
    q: str = Query("", max_length=80, description="港股代码、中文名或英文名"),
    limit: int = Query(8, ge=1, le=20),
):
    """从本地主数据索引快速搜索港股。"""
    return await hk_market_service.search_stocks(q, limit=limit)


@router.get("/stocks/{code}/history", response_model=KlineData)
async def get_hk_stock_history(
    code: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly|annual)$"),
    adjust: str = Query("none", pattern=r"^(none|qfq|hfq|)$"),
    start_date: str = Query("", description="起始日期 YYYYMMDD 或 YYYY-MM-DD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD 或 YYYY-MM-DD"),
):
    """获取新浪港股个股历史行情。"""
    return await hk_market_service.get_stock_history(
        code,
        period=period,
        adjust=adjust or "none",
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/stocks/{code}/intraday", response_model=IntradayData)
async def get_hk_stock_intraday(code: str):
    """获取港股个股分时行情数据。"""
    return await get_intraday(code)


@router.get("/stocks/{code}/indicators", response_model=TechnicalIndicators)
async def get_hk_stock_indicators(
    code: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly|annual)$"),
    start_date: str = Query("", description="起始日期，留空默认一年前"),
    end_date: str = Query("", description="结束日期，留空默认当天"),
):
    """获取港股指定周期的技术指标（均线、MACD、RSI、布林带、KDJ、成交量均线）。"""
    return await get_technical_indicators_service(
        code, period=period, start_date=start_date, end_date=end_date
    )


@router.get("/stocks/{code}/valuation", response_model=HKStockValuation)
async def get_hk_stock_valuation(code: str):
    """获取港股个股估值与市值指标（市盈率 TTM、市净率、总市值、流通市值等）。"""
    return await hk_market_service.get_stock_valuation(code)


@router.get("/indices/realtime", response_model=MarketIndices)
async def get_hk_index_quotes(
    symbols: str = Query("", description="逗号分隔的指数代码：HSI,HSCEI,HSTECH"),
):
    """获取新浪港股核心指数实时行情。"""
    return await hk_market_service.get_index_quotes(_split_csv(symbols))


@router.get("/indices/{symbol}/history", response_model=KlineData)
async def get_hk_index_history(
    symbol: str,
    period: str = Query("daily", pattern=r"^(daily|weekly|monthly|annual)$"),
    start_date: str = Query("", description="起始日期 YYYYMMDD 或 YYYY-MM-DD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD 或 YYYY-MM-DD"),
):
    """获取新浪港股指数历史行情。"""
    return await hk_market_service.get_index_history(
        symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
