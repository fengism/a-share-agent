"""市场行情与资金流 HTTP API。"""

from datetime import date as Date

from fastapi import APIRouter, Query

from app.domain.market import KlineData, MarketIndices
from app.financial_data.market.public import (
    DragonTigerItem,
    HsgtFlowHistoryItem,
    HsgtFlowResponse,
    IndexIntradayData,
    IndustryRankings,
    MarketEmotion,
    MarketLimitHistoryCategory,
    MarketLimitHistoryResponse,
    MarketLimitUpLadderResponse,
    MarketMainlineResponse,
    MarketMarginResponse,
    MarketSectorStocksHistoryResponse,
    MarketVolumeResponse,
    MarketWindResponse,
    MarketWindStocksResponse,
    ThsHotPlate,
    ThsHotStock,
    TradingCalendarResponse,
)
from app.financial_data.market.public import get_dragon_tiger_list as get_dragon_tiger_list_service
from app.financial_data.market.public import get_hot_stocks as get_hot_stocks_service
from app.financial_data.market.public import get_hsgt_flow as get_hsgt_flow_service
from app.financial_data.market.public import get_hsgt_flow_history as get_hsgt_flow_history_service
from app.financial_data.market.public import get_index_intraday as get_index_intraday_service
from app.financial_data.market.public import get_index_kline as get_index_kline_service
from app.financial_data.market.public import get_indices as get_indices_service
from app.financial_data.market.public import get_industry_rankings as get_industry_rankings_service
from app.financial_data.market.public import get_limit_history as get_limit_history_service
from app.financial_data.market.public import get_limit_up_ladder as get_limit_up_ladder_service
from app.financial_data.market.public import get_market_emotion as get_market_emotion_service
from app.financial_data.market.public import get_market_mainline as get_market_mainline_service
from app.financial_data.market.public import get_market_margin as get_market_margin_service
from app.financial_data.market.public import get_market_volume as get_market_volume_service
from app.financial_data.market.public import get_market_wind as get_market_wind_service
from app.financial_data.market.public import get_market_wind_stocks as get_market_wind_stocks_service
from app.financial_data.market.public import get_sector_stocks_history as get_sector_stocks_history_service
from app.financial_data.market.public import get_ths_hot_concept as get_ths_hot_concept_service
from app.financial_data.market.public import get_ths_hot_industry as get_ths_hot_industry_service
from app.financial_data.market.public import get_trading_calendar_view as get_trading_calendar_view_service

router = APIRouter()


@router.get("/emotion", response_model=MarketEmotion)
async def get_market_emotion():
    """获取财联社实时市场情绪。"""
    return await get_market_emotion_service()


@router.get("/mainline", response_model=MarketMainlineResponse)
async def get_market_mainline():
    """获取财联社今日主线机会。"""
    return await get_market_mainline_service()


@router.get("/limit-up-ladder", response_model=MarketLimitUpLadderResponse)
async def get_limit_up_ladder(
    date: Date | None = Query(None, description="查询日期 YYYY-MM-DD，默认当天"),
):
    """获取开盘红涨停天梯与板块涨停分布。"""
    return await get_limit_up_ladder_service(date)


@router.get("/limit-history", response_model=MarketLimitHistoryResponse)
async def get_limit_history(
    date: Date = Query(..., description="历史日期 YYYY-MM-DD，必须早于今天"),
    category: MarketLimitHistoryCategory = Query(
        ...,
        description="limit_up / limit_down / wind_vane",
    ),
):
    """获取开盘红历史涨停、跌停或风向标列表。"""
    return await get_limit_history_service(date, category)


@router.get("/sector-stocks-history", response_model=MarketSectorStocksHistoryResponse)
async def get_sector_stocks_history(
    date: Date = Query(..., description="历史日期 YYYY-MM-DD，必须早于今天"),
    plate_id: str = Query(..., min_length=1, description="开盘红板块 ID，例如 881169"),
):
    """获取开盘红板块在指定历史日期的成分股列表。"""
    return await get_sector_stocks_history_service(date, plate_id)


@router.get("/trading-calendar", response_model=TradingCalendarResponse)
async def get_trading_calendar(
    start_date: Date | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Date | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """获取 A 股交易日历（区间列表与今日交易状态）。"""
    return await get_trading_calendar_view_service(start_date, end_date)


@router.get("/margin", response_model=MarketMarginResponse)
async def get_market_margin(
    days: int = Query(240, description="返回的交易日数量，30-500"),
):
    """获取沪深两市融资融券历史合计（日级，单位亿元）。"""
    return await get_market_margin_service(days)


@router.get("/today-wind", response_model=MarketWindResponse)
async def get_market_wind():
    """获取财联社今日风口板块。"""
    return await get_market_wind_service()


@router.get("/today-wind/{plate_code}/stocks", response_model=MarketWindStocksResponse)
async def get_market_wind_stocks(plate_code: str):
    """获取指定风口板块的龙头股。"""
    return await get_market_wind_stocks_service(plate_code)


@router.get("/indices", response_model=MarketIndices)
async def get_indices():
    """获取主要大盘指数实时行情。"""
    return await get_indices_service()


@router.get("/index-intraday", response_model=IndexIntradayData)
async def get_index_intraday(
    symbol: str = Query(..., pattern=r"^\d{6}$", description="指数代码，例如 000001"),
):
    """获取主要大盘指数当前交易日分时行情。"""
    return await get_index_intraday_service(symbol)


@router.get("/index-kline", response_model=KlineData)
async def get_index_kline(
    symbol: str = Query(..., description="指数代码，例如 000001"),
    period: str = Query("daily", description="daily / weekly / monthly"),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """获取指数 K 线数据。"""
    return await get_index_kline_service(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/volume", response_model=MarketVolumeResponse)
async def get_volume(start_date: str = Query(""), end_date: str = Query("")):
    """获取大盘成交量历史数据。"""
    return await get_market_volume_service(start_date, end_date)


@router.get("/hot-stocks", response_model=list[ThsHotStock])
async def get_hot_stocks():
    """获取热门股排名。"""
    return await get_hot_stocks_service()


@router.get("/hot-rank/ths", response_model=list[ThsHotStock])
async def get_ths_hot_rank():
    """获取同花顺热股榜单。"""
    return await get_hot_stocks_service()


@router.get("/hot-rank/ths/concept", response_model=list[ThsHotPlate])
async def get_ths_hot_concept():
    """获取同花顺热门概念榜。"""
    return await get_ths_hot_concept_service()


@router.get("/hot-rank/ths/industry", response_model=list[ThsHotPlate])
async def get_ths_hot_industry():
    """获取同花顺热门行业榜。"""
    return await get_ths_hot_industry_service()


@router.get("/dragon-tiger", response_model=list[DragonTigerItem])
async def get_dragon_tiger_list(
    report_date: str = Query("", description="报告日期 YYYY-MM-DD，默认当天"),
):
    """获取龙虎榜列表。"""
    return await get_dragon_tiger_list_service(report_date or None)


@router.get("/industry-rankings", response_model=IndustryRankings)
async def get_industry_rankings(
    date: Date | None = Query(None, description="查询日期 YYYY-MM-DD，默认今天"),
):
    """获取行业板块涨跌与资金排名。"""
    return await get_industry_rankings_service(date)


@router.get("/hsgt-flow", response_model=HsgtFlowResponse)
async def get_hsgt_flow():
    """获取沪深股通分钟级资金流向。"""
    return await get_hsgt_flow_service()


@router.get("/hsgt-flow/history", response_model=list[HsgtFlowHistoryItem])
async def get_hsgt_flow_history(days: int = Query(30, description="查询天数")):
    """读取沪深股通历史分钟流向数据。"""
    return await get_hsgt_flow_history_service(days)
