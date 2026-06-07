import logging

from fastapi import APIRouter, HTTPException

from app.routers.errors import run_endpoint

from app.models.screener import (
    ScreenerFilter,
    ScreenerResult,
    ValuationPercentileRequest,
    ValuationPercentileResult,
)
from app.services.screener.industry import get_industry_list
from app.services.screener.percentiles import compute_percentiles as compute_percentiles_service
from app.services.screener.screening import screen_stocks as screen_stocks_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/screen", response_model=ScreenerResult)
async def screen_stocks(filters: ScreenerFilter):
    """根据筛选条件返回匹配股票分页结果。

    Param:
        filters: ScreenerFilter 请求体，含估值区间、行业、分页等参数。
    Return:
        ScreenerResult: 符合条件的股票列表与总数。
    """
    logger.info(f"选股筛选: PE={filters.pe_min}-{filters.pe_max}, PB={filters.pb_min}-{filters.pb_max}, "
                f"行业={filters.industries}, page={filters.page}")

    async def execute():
        """执行底层选股服务并记录命中数。

        Return:
            ScreenerResult: 服务层返回的筛选结果。
        """
        result = await screen_stocks_service(filters)
        logger.info(f"筛选结果: {result.total} 只, 返回第 {filters.page} 页")
        return result

    return await run_endpoint("筛选", execute)


@router.get("/industries", response_model=list[str])
async def get_industries():
    """获取可用于筛选的行业名称列表。

    Return:
        list[str]: 行业名称集合。
    """
    return await run_endpoint("获取行业列表", get_industry_list)


@router.post("/percentile", response_model=ValuationPercentileResult)
async def compute_percentiles(request: ValuationPercentileRequest):
    """批量计算给定股票的估值历史百分位。

    Param:
        request: ValuationPercentileRequest 请求体，含代码、指标和周期；最多 50 只。
    Return:
        ValuationPercentileResult: 每只股票的估值百分位条目集合。
    """
    if len(request.codes) > 50:
        raise HTTPException(status_code=400, detail="单次最多50只股票")
    logger.info(f"计算估值百分位: {len(request.codes)} 只, indicator={request.indicator}")

    async def execute():
        """调用估值百分位服务并组装响应模型。

        Return:
            ValuationPercentileResult: 含 items 列表的结果对象。
        """
        items = await compute_percentiles_service(
            codes=request.codes,
            indicator=request.indicator,
            period=request.period,
        )
        return ValuationPercentileResult(items=items)

    return await run_endpoint("估值百分位计算", execute)
