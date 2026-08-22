"""宏观数据 HTTP API。"""

import logging

from fastapi import APIRouter, Query

from app.financial_data.market.public import MacroAllDataResponse, MacroUsDataResponse
from app.financial_data.market.public import get_macro_all_data as get_macro_all_data_service
from app.financial_data.market.public import get_us_macro_data as get_us_macro_data_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/all", response_model=MacroAllDataResponse)
async def get_macro_all(
    force_refresh: bool = Query(False, description="忽略缓存并重新获取宏观数据"),
):
    """获取全量宏观经济指标数据。"""
    logger.info("获取全量宏观数据 force_refresh=%s", force_refresh)
    return await get_macro_all_data_service(force_refresh=force_refresh)


@router.get("/us", response_model=MacroUsDataResponse)
async def get_us_macro(
    force_refresh: bool = Query(False, description="忽略缓存并重新获取美国宏观数据"),
):
    return await get_us_macro_data_service(force_refresh=force_refresh)
