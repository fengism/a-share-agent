import logging

from fastapi import APIRouter, HTTPException

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
    try:
        return await get_macro_all_data_service()
    except Exception as e:
        logger.error(f"获取全量宏观数据失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取宏观数据失败: {e}")
