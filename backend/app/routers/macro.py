import logging

from fastapi import APIRouter, HTTPException
from app.routers.errors import run_endpoint

from app.services.market.macro import get_macro_all_data as get_macro_all_data_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/all")
async def get_macro_all():
    """获取全量宏观经济指标数据（6大类）。

    Return:
        dict: 物价/景气/货币/利率/增速/外贸 六大板块的最新值与趋势数据。
    """
    logger.info("获取全量宏观数据")
    return await run_endpoint("获取全量宏观数据", get_macro_all_data_service)
