"""个股资料与对比 HTTP API。"""

import logging

from fastapi import APIRouter, Query

from app.domain.stock import StockSearchItem
from app.financial_data.stock.public import StockBasicInfo, StockCompareItem
from app.financial_data.stock.public import get_basic_info as get_basic_info_service
from app.financial_data.stock.public import search_stocks as search_stock_items
from app.modules.stock_comparison.public import compare_stocks as compare_stocks_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search", response_model=list[StockSearchItem])
async def search_stocks(q: str = Query(..., min_length=1, description="股票名称或代码")):
    """按名称或代码模糊搜索股票。"""
    result = await search_stock_items(q)
    logger.info("搜索结果: q=%s, 匹配%d条", q, len(result))
    return result


@router.get("/{code}/info", response_model=StockBasicInfo)
async def get_stock_info(code: str):
    """获取个股基本资料。"""
    return await get_basic_info_service(code)


@router.get("/compare", response_model=list[StockCompareItem], response_model_exclude_unset=True)
async def get_compare(codes: str = Query(..., description="逗号分隔的股票代码，如 600519,000858")):
    """多股对比分析。"""
    return await compare_stocks_service(codes)
