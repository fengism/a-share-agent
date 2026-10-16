"""宏观数据 HTTP API。"""

import logging

from fastapi import APIRouter, Query

from app.financial_data.market.public import (
    CommoditiesResponse,
    CustomsTradeDataResponse,
    GlobalMacroRatesResponse,
    MacroAllDataResponse,
    MacroAnalysisResponse,
    MacroFeedResponse,
    MacroUsDataResponse,
    SgeGoldResponse,
    TreasuryYieldsResponse,
)
from app.financial_data.market.public import (
    get_commodity_spot_prices as get_commodity_spot_prices_service,
)
from app.financial_data.market.public import (
    get_customs_trade_data as get_customs_trade_data_service,
)
from app.financial_data.market.public import (
    get_global_macro_rates as get_global_macro_rates_service,
)
from app.financial_data.market.public import get_macro_all_data as get_macro_all_data_service
from app.financial_data.market.public import get_macro_analysis as get_macro_analysis_service
from app.financial_data.market.public import get_macro_feed as get_macro_feed_service
from app.financial_data.market.public import get_sge_gold_history as get_sge_gold_history_service
from app.financial_data.market.public import (
    get_treasury_yield_curve as get_treasury_yield_curve_service,
)
from app.financial_data.market.public import get_us_macro_data as get_us_macro_data_service
from app.financial_data.market.public import trigger_macro_prewarm as trigger_macro_prewarm_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/all", response_model=MacroAllDataResponse)
async def get_macro_all(
    force_refresh: bool = Query(False, description="忽略缓存并重新获取宏观数据"),
):
    """获取全量宏观经济指标数据。"""
    logger.info("获取全量宏观数据 force_refresh=%s", force_refresh)
    return await get_macro_all_data_service(force_refresh=force_refresh)


@router.get("/feed", response_model=MacroFeedResponse)
async def get_macro_feed(
    days: int = Query(31, ge=1, le=180, description="回溯自然日天数"),
):
    """获取资讯页宏观数据：统计局最新发布、央行新闻/政策解读与利率。"""
    return await get_macro_feed_service(days=days)


@router.get("/analysis", response_model=MacroAnalysisResponse)
async def get_macro_analysis(
    days: int = Query(31, ge=1, le=180, description="回溯自然日天数"),
):
    """获取宏观 AI 解读：综述与按时间梳理的事件系列（历史条目走缓存）。

    命中未解读的新条目时顺带触发后台预热，新条目数秒内即可补齐 AI 解读。
    """
    response = await get_macro_analysis_service(days=days)
    if response.pending_count:
        trigger_macro_prewarm_service(days)
    return response


@router.get("/us", response_model=MacroUsDataResponse)
async def get_us_macro(
    force_refresh: bool = Query(False, description="忽略缓存并重新获取美国宏观数据"),
):
    return await get_us_macro_data_service(force_refresh=force_refresh)


@router.get("/global-rates", response_model=GlobalMacroRatesResponse)
async def get_global_rates():
    """获取全球宏观利率、中美10Y国债收益率与汇率流动性看板。"""
    return await get_global_macro_rates_service()


@router.get("/treasury-yields", response_model=TreasuryYieldsResponse)
async def get_treasury_yields(
    page_size: int = Query(300, description="历史曲线记录条数", ge=10, le=1000),
):
    """获取中美国债收益率历史曲线、期限结构与中美利差数据。"""
    return await get_treasury_yield_curve_service(page_size=page_size)


@router.get("/commodities", response_model=CommoditiesResponse)
async def get_commodities(
    symbol: str = Query("", description="大宗商品名称，省略返回全量概览"),
):
    """获取大宗商品期货最近报价与静态产业映射，不含现货/基差。"""
    return await get_commodity_spot_prices_service(symbol=symbol)


@router.get("/customs-trade", response_model=CustomsTradeDataResponse)
async def get_customs_trade(
    commodity: str = Query("", description="重点进出口商品名称，省略返回全量概览"),
):
    """获取全国月度进出口总况及静态商品介绍，不含细分商品量价。"""
    return await get_customs_trade_data_service(commodity=commodity)


@router.get("/sge-gold", response_model=SgeGoldResponse)
async def get_sge_gold(
    symbol: str = Query("Au99.99", description="上海黄金交易所品种代码"),
):
    """获取上海黄金交易所指定品种的历史行情。"""
    return await get_sge_gold_history_service(symbol=symbol)
