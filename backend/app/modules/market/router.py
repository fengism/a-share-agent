"""市场产品 API。"""

import logging

from fastapi import APIRouter, Depends, Query

from app.configuration import get_settings
from app.contracts.market import KlineData, MarketIndices
from app.contracts.search import NewsSearchItem
from app.core.exceptions import InvalidRequestError
from app.market_data.market.public import (
    DragonTigerItem,
    HsgtFlowHistoryItem,
    HsgtFlowResponse,
    IndustryRankings,
    MacroAllDataResponse,
    MarketVolumeSeriesItem,
    ThsHotPlate,
    ThsHotStock,
    refresh_twitter_feed_now,
)
from app.market_data.market.public import get_dragon_tiger_list as get_dragon_tiger_list_service
from app.market_data.market.public import get_hot_stocks as get_hot_stocks_service
from app.market_data.market.public import get_hsgt_flow as get_hsgt_flow_service
from app.market_data.market.public import get_hsgt_flow_history as get_hsgt_flow_history_service
from app.market_data.market.public import get_index_kline as get_index_kline_service
from app.market_data.market.public import get_indices as get_indices_service
from app.market_data.market.public import get_industry_rankings as get_industry_rankings_service
from app.market_data.market.public import get_macro_all_data as get_macro_all_data_service
from app.market_data.market.public import get_market_feed as get_market_feed_service
from app.market_data.market.public import get_market_kuaixun as get_market_kuaixun_service
from app.market_data.market.public import get_market_other_news as get_market_other_news_service
from app.market_data.market.public import get_market_volume as get_market_volume_service
from app.market_data.market.public import get_ths_hot_concept as get_ths_hot_concept_service
from app.market_data.market.public import get_ths_hot_industry as get_ths_hot_industry_service
from app.market_data.market.public import get_twitter_feed as get_twitter_feed_service
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.market.content.analysis import analyze_market_news as analyze_market_news_service
from app.modules.market.content.schemas import (
    NewsAnalysisResponse,
    TwitterAnalysisResult,
    TwitterFeedRefreshResponse,
)
from app.modules.market.content.twitter import analyze_twitter_user

logger = logging.getLogger(__name__)

router = APIRouter()
macro_router = APIRouter()


@router.get("/indices", response_model=MarketIndices)
async def get_indices():
    """获取主要大盘指数实时行情。

    Return:
        list[dict] | dict: 上证、深证等核心指数的当前点位与涨跌幅数据。
    """
    return await get_indices_service()


@router.get("/index-kline", response_model=KlineData)
async def get_index_kline(
    symbol: str = Query(..., description="指数代码，例如 000001"),
    period: str = Query("daily", description="daily / weekly / monthly"),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """获取指数 K 线数据。

    Param:
        symbol: 指数代码（查询参数），例如 000001。
        period: K 线周期（查询参数），daily / weekly / monthly。
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空表示至今天。
    Return:
        dict: 指数 K 线时序数据，包含日期、开高低收和成交量。
    """

    return await get_index_kline_service(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/volume", response_model=list[MarketVolumeSeriesItem])
async def get_volume(start_date: str = Query(""), end_date: str = Query("")):
    """获取大盘成交量历史数据。

    Param:
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空。
    Return:
        dict: 大盘成交量、成交额时序数据。
    """
    return await get_market_volume_service(start_date, end_date)


@router.get("/hot-stocks", response_model=list[ThsHotStock])
async def get_hot_stocks():
    """获取热门股排名（默认同花顺数据源）。

    Return:
        list[dict]: 热门股排序与对应人气指标。
    """
    return await get_hot_stocks_service()


@router.get("/hot-rank/ths", response_model=list[ThsHotStock])
async def get_ths_hot_rank():
    """获取同花顺热股榜单（与 /hot-stocks 等价）。

    Return:
        list[dict]: 同花顺热股榜数据。
    """
    return await get_hot_stocks_service()


@router.get("/hot-rank/ths/concept", response_model=list[ThsHotPlate])
async def get_ths_hot_concept():
    """获取同花顺热门概念榜。

    Return:
        list[dict]: 热门概念名称与热度指标。
    """
    return await get_ths_hot_concept_service()


@router.get("/hot-rank/ths/industry", response_model=list[ThsHotPlate])
async def get_ths_hot_industry():
    """获取同花顺热门行业榜。

    Return:
        list[dict]: 热门行业名称与对应热度指标。
    """
    return await get_ths_hot_industry_service()


@router.get("/dragon-tiger", response_model=list[DragonTigerItem])
async def get_dragon_tiger_list(report_date: str = Query("", description="报告日期 YYYY-MM-DD，默认当天")):
    """获取龙虎榜列表。

    Param:
        report_date: 报告日期（查询参数），格式 YYYY-MM-DD，留空表示当天。
    Return:
        list[dict]: 龙虎榜个股摘要。
    """
    return await get_dragon_tiger_list_service(report_date or None)


@router.get("/industry-rankings", response_model=IndustryRankings)
async def get_industry_rankings():
    """获取行业板块涨跌幅排名。

    Return:
        list[dict]: 行业名称、涨跌幅及成交活跃度排序。
    """
    return await get_industry_rankings_service()


@router.get("/hsgt-flow", response_model=HsgtFlowResponse)
async def get_hsgt_flow():
    """获取沪深股通分钟级资金流向。"""
    return await get_hsgt_flow_service()


@router.get("/hsgt-flow/history", response_model=list[HsgtFlowHistoryItem])
async def get_hsgt_flow_history(days: int = Query(30, description="查询天数")):
    """读取沪深股通历史分钟流向数据。"""
    return await get_hsgt_flow_history_service(days)


@router.get("/feed", response_model=list[NewsSearchItem])
async def get_market_feed():
    """获取 24 小时市场新闻流。

    Return:
        list[dict] | dict: 综合多源的新闻列表，按时间倒序。
    """
    return await get_market_feed_service()


@router.get("/kuaixun", response_model=list[NewsSearchItem])
async def get_market_kuaixun():
    """获取 7×24 快讯流（多源合并去重，分钟级刷新）。

    Return:
        list[dict]: 快讯列表，source 统一为 "7×24 快讯"。
    """
    return await get_market_kuaixun_service()


@router.get("/other-news", response_model=list[NewsSearchItem])
async def get_market_other_news():
    """获取非快讯类新闻（30 分钟刷新）。

    Return:
        list[dict]: 新闻列表，按时间倒序。
    """
    return await get_market_other_news_service()


@router.get("/twitter-feed", response_model=list[NewsSearchItem])
async def get_twitter_feed():
    """获取 Twitter/X 财经账号的最新推文和文章。

    Return:
        list[dict]: Twitter 资讯列表，按时间倒序。
    """
    return await get_twitter_feed_service()


@router.post("/twitter-feed/refresh", response_model=TwitterFeedRefreshResponse)
async def refresh_twitter_feed():
    """手动触发 Twitter 资讯刷新。

    立即从 Twitter provider 拉取最新推文并写入数据库。

    Return:
        dict: 刷新结果 {status, authors, posts_count}
    """
    return await refresh_twitter_feed_now()


@router.get("/news-analysis", response_model=NewsAnalysisResponse)
async def get_news_analysis(user: AuthenticatedUser = Depends(require_active_user)):
    """获取由 LLM 生成的市场资讯综合分析。

    Return:
        dict: AI 汇总的市场资讯解读与要点。
    """
    return await analyze_market_news_service(user["id"])


@router.get("/twitter-analyze", response_model=TwitterAnalysisResult)
async def get_twitter_analyze(
    username: str = Query(..., description="Twitter 用户名，如 qinbafrank"),
    force_refresh: bool = Query(False, description="忽略缓存并重新生成分析"),
    _user: AuthenticatedUser = Depends(require_active_user),
):
    """分析已配置 Twitter 用户的最新推文和文章并生成 AI 报告。"""
    normalized = username.strip().removeprefix("@").lower()
    configured = {
        account.strip().removeprefix("@").lower(): account.strip().removeprefix("@")
        for account in get_settings().twitter_feeds
        if account.strip().removeprefix("@")
    }
    if not normalized or normalized not in configured:
        raise InvalidRequestError(
            "仅支持分析设置中已配置的 Twitter 账号",
            code="invalid_request",
        )
    configured_username = configured[normalized]
    return await analyze_twitter_user(
        configured_username,
        force_refresh=force_refresh,
    )


@macro_router.get("/all", response_model=MacroAllDataResponse)
async def get_macro_all(
    force_refresh: bool = Query(False, description="忽略缓存并重新获取宏观数据"),
):
    """获取全量宏观经济指标数据（6大类）。

    Return:
        dict: 物价/景气/货币/利率/增速/外贸 六大板块的最新值与趋势数据。
    """
    logger.info("获取全量宏观数据 force_refresh=%s", force_refresh)
    return await get_macro_all_data_service(force_refresh=force_refresh)
