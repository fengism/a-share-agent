"""股票筛选 HTTP API。"""

import logging

from fastapi import APIRouter

from app.api.errors import BadRequestError
from app.modules.screener.public import (
    ScreenerFilter,
    ScreenerResult,
    ScreenerStrategyPreset,
    ScreenerStrategyRequest,
    ScreenerStrategyResult,
    ValuationPercentileRequest,
    ValuationPercentileResult,
    get_industry_list,
    list_screener_strategies,
    screen_candidates_by_strategy,
)
from app.modules.screener.public import compute_percentiles as compute_percentiles_service
from app.modules.screener.public import screen_stocks as screen_stocks_service

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

    result = await screen_stocks_service(filters)
    logger.info(f"筛选结果: {result.total} 只, 返回第 {filters.page} 页")
    return result


@router.get("/industries", response_model=list[str])
async def get_industries(level: int | None = None):
    """获取可用于筛选的行业名称列表。

    Param:
        level: 可选的申万级别 (1, 2, 3)，不传时返回全级别去重行业列表。
    Return:
        list[str]: 行业名称集合。
    """
    return await get_industry_list(level=level)


@router.get("/concepts", response_model=list[str])
async def get_concepts():
    """获取可用于筛选的概念名称列表。

    Return:
        list[str]: 概念名称集合。
    """
    from app.core.concurrency.rate_limiter import call_blocking
    from app.modules.stock_concept.public import get_all_concepts

    items = await call_blocking(get_all_concepts, limit=2000)
    return [item["name"] for item in items]


@router.post("/percentile", response_model=ValuationPercentileResult)
async def compute_percentiles(request: ValuationPercentileRequest):
    """批量计算给定股票的估值历史百分位。

    Param:
        request: ValuationPercentileRequest 请求体，含代码、指标和周期；最多 50 只。
    Return:
        ValuationPercentileResult: 每只股票的估值百分位条目集合。
    """
    if len(request.codes) > 50:
        raise BadRequestError("单次最多50只股票", code="screener.too_many_codes")
    logger.info(f"计算估值百分位: {len(request.codes)} 只, indicator={request.indicator}")

    items = await compute_percentiles_service(
        codes=request.codes,
        indicator=request.indicator,
        period=request.period,
    )
    return ValuationPercentileResult(items=items)


@router.get("/strategies", response_model=list[ScreenerStrategyPreset])
async def get_screener_strategies():
    return list_screener_strategies()


@router.post("/strategy-screen", response_model=ScreenerStrategyResult)
async def apply_screener_strategy(request: ScreenerStrategyRequest):
    try:
        return await screen_candidates_by_strategy(request)
    except ValueError as error:
        raise BadRequestError(str(error), code="screener.invalid_strategy") from error
