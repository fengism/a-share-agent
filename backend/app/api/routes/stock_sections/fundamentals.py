"""个股财务与估值 HTTP API。"""

from fastapi import APIRouter, Query

from app.financial_data.stock.public import (
    FinancialMetrics,
    FinancialStatementRow,
    StockValuation,
    ValuationDetail,
)
from app.financial_data.stock.public import get_financial as get_financial_service
from app.financial_data.stock.public import get_financial_metrics as get_financial_metrics_service
from app.financial_data.stock.public import get_valuation as get_valuation_service
from app.financial_data.stock.public import get_valuation_detail as get_valuation_detail_service

router = APIRouter()


@router.get("/{code}/financial", response_model=list[FinancialStatementRow])
async def get_financial(
    code: str,
    type: str = Query("balance", pattern="^(balance|profit|cashflow)$"),
):
    """获取个股财务报表数据。"""
    return await get_financial_service(code, type)


@router.get("/{code}/financial-metrics", response_model=FinancialMetrics)
async def get_financial_metrics(code: str):
    """获取个股关键财务指标汇总。"""
    return await get_financial_metrics_service(code)


@router.get("/{code}/valuation", response_model=StockValuation)
async def get_valuation(code: str):
    """获取个股估值数据。"""
    return await get_valuation_service(code)


@router.get("/{code}/valuation-detail", response_model=ValuationDetail)
async def get_valuation_detail(code: str):
    """获取个股估值详情。"""
    return await get_valuation_detail_service(code)
