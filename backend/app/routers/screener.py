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
    logger.info(f"选股筛选: PE={filters.pe_min}-{filters.pe_max}, PB={filters.pb_min}-{filters.pb_max}, "
                f"行业={filters.industries}, page={filters.page}")

    async def execute():
        result = await screen_stocks_service(filters)
        logger.info(f"筛选结果: {result.total} 只, 返回第 {filters.page} 页")
        return result

    return await run_endpoint("筛选", execute)


@router.get("/industries", response_model=list[str])
async def get_industries():
    return await run_endpoint("获取行业列表", get_industry_list)


@router.post("/percentile", response_model=ValuationPercentileResult)
async def compute_percentiles(request: ValuationPercentileRequest):
    if len(request.codes) > 50:
        raise HTTPException(status_code=400, detail="单次最多50只股票")
    logger.info(f"计算估值百分位: {len(request.codes)} 只, indicator={request.indicator}")

    async def execute():
        items = await compute_percentiles_service(
            codes=request.codes,
            indicator=request.indicator,
            period=request.period,
        )
        return ValuationPercentileResult(items=items)

    return await run_endpoint("估值百分位计算", execute)
