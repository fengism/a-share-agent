"""市场相关 API 端点：指数、成交量、热点、龙虎榜列表、新闻等。"""

import logging

from fastapi import APIRouter, Query

from app.routers.errors import run_endpoint
from app.services.market.dragon_tiger import (
    get_dragon_tiger_list as get_dragon_tiger_list_service,
)
from app.services.market.hot_rank import (
    get_hot_stocks as get_hot_stocks_service,
    get_ths_hot_concept as get_ths_hot_concept_service,
    get_ths_hot_industry as get_ths_hot_industry_service,
)
from app.services.market.fund_flow import (
    get_hsgt_flow as get_hsgt_flow_service,
    get_hsgt_flow_history as get_hsgt_flow_history_service,
)
from app.services.market.index_kline import get_index_kline as get_index_kline_service
from app.services.market.indices import get_indices as get_indices_service
from app.services.market.volume import get_market_volume as get_market_volume_service
from app.services.market.news import get_market_feed as get_market_feed_service
from app.services.market.news import get_market_kuaixun as get_market_kuaixun_service
from app.services.market.news import get_market_other_news as get_market_other_news_service
from app.services.market.news import get_twitter_feed as get_twitter_feed_service
from app.services.market.sector import get_industry_rankings as get_industry_rankings_service
from app.services.market.news_analysis import analyze_market_news as analyze_market_news_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/indices")
async def get_indices():
    """获取主要大盘指数实时行情。

    Return:
        list[dict] | dict: 上证、深证等核心指数的当前点位与涨跌幅数据。
    """
    return await run_endpoint("获取大盘指数", get_indices_service)


@router.get("/index-kline")
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
    async def execute():
        return await get_index_kline_service(
            symbol=symbol, period=period, start_date=start_date, end_date=end_date,
        )
    return await run_endpoint("获取指数K线", execute)


@router.get("/volume")
async def get_volume(start_date: str = Query(""), end_date: str = Query("")):
    """获取大盘成交量历史数据。

    Param:
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空。
    Return:
        dict: 大盘成交量、成交额时序数据。
    """
    return await run_endpoint("获取大盘成交量", lambda: get_market_volume_service(start_date, end_date))


@router.get("/hsgt-flow")
async def get_hsgt_flow():
    """获取沪深股通分钟级资金流向。

    Return:
        dict: 当日沪股通、深股通的分钟级净流入序列。
    """
    return await run_endpoint("获取沪深股通分钟流向", get_hsgt_flow_service)


@router.get("/hsgt-flow/history")
async def get_hsgt_flow_history(days: int = Query(30, description="查询天数")):
    """读取沪深股通历史分钟流向数据。

    Param:
        days: 查询天数（查询参数），默认 30 天。
    Return:
        list[dict]: 每天包含日期、更新时间和分钟级 points 序列。
    """
    return await run_endpoint("获取沪深股通历史数据", lambda: get_hsgt_flow_history_service(days))


@router.get("/hot-stocks")
async def get_hot_stocks():
    """获取热门股排名（默认同花顺数据源）。

    Return:
        list[dict]: 热门股排序与对应人气指标。
    """
    return await run_endpoint("获取热门股排名", get_hot_stocks_service)


@router.get("/hot-rank/ths")
async def get_ths_hot_rank():
    """获取同花顺热股榜单（与 /hot-stocks 等价）。

    Return:
        list[dict]: 同花顺热股榜数据。
    """
    return await run_endpoint("获取同花顺热股榜单", get_hot_stocks_service)


@router.get("/hot-rank/ths/concept")
async def get_ths_hot_concept():
    """获取同花顺热门概念榜。

    Return:
        list[dict]: 热门概念名称与热度指标。
    """
    return await run_endpoint("获取同花顺热门概念", get_ths_hot_concept_service)


@router.get("/hot-rank/ths/industry")
async def get_ths_hot_industry():
    """获取同花顺热门行业榜。

    Return:
        list[dict]: 热门行业名称与对应热度指标。
    """
    return await run_endpoint("获取同花顺热门行业", get_ths_hot_industry_service)


@router.get("/dragon-tiger")
async def get_dragon_tiger_list(report_date: str = Query("", description="报告日期 YYYY-MM-DD，默认当天")):
    """获取龙虎榜列表。

    Param:
        report_date: 报告日期（查询参数），格式 YYYY-MM-DD，留空表示当天。
    Return:
        list[dict]: 龙虎榜个股摘要。
    """
    return await run_endpoint("获取龙虎榜", lambda: get_dragon_tiger_list_service(report_date or None))


@router.get("/feed")
async def get_market_feed():
    """获取 24 小时市场新闻流。

    Return:
        list[dict] | dict: 综合多源的新闻列表，按时间倒序。
    """
    return await run_endpoint("获取新闻流", get_market_feed_service)


@router.get("/kuaixun")
async def get_market_kuaixun():
    """获取 7×24 快讯流（多源合并去重，分钟级刷新）。

    Return:
        list[dict]: 快讯列表，source 统一为 "7×24 快讯"。
    """
    return await run_endpoint("获取快讯流", get_market_kuaixun_service)


@router.get("/other-news")
async def get_market_other_news():
    """获取非快讯类新闻（30 分钟刷新）。

    Return:
        list[dict]: 新闻列表，按时间倒序。
    """
    return await run_endpoint("获取其他新闻", get_market_other_news_service)


@router.get("/twitter-feed")
async def get_twitter_feed():
    """获取 Twitter/X 财经账号的最新推文和文章。

    Return:
        list[dict]: Twitter 资讯列表，按时间倒序。
    """
    return await run_endpoint("获取 Twitter 资讯", get_twitter_feed_service)


@router.get("/industry-rankings")
async def get_industry_rankings():
    """获取行业板块涨跌幅排名。

    Return:
        list[dict]: 行业名称、涨跌幅及成交活跃度排序。
    """
    return await run_endpoint("获取行业板块涨跌幅排名", get_industry_rankings_service)


@router.get("/news-analysis")
async def get_news_analysis():
    """获取由 LLM 生成的市场资讯综合分析。

    Return:
        dict: AI 汇总的市场资讯解读与要点。
    """
    return await run_endpoint("获取AI资讯分析", analyze_market_news_service)
