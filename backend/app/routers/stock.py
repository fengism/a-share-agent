"""个股相关 API 端点：搜索、行情、K线、财务、估值、新闻、情绪、技术指标。"""

import logging

from fastapi import APIRouter, Query

from app.models.stock import FinancialMetrics, IntradayData, KlineData, StockBasicInfo, StockSearchItem, ValuationDetail
from app.routers.errors import run_endpoint
from app.services import technical
from app.services.stock.news import get_stock_news as get_stock_news_service
from app.services.stock.news import get_stock_news_categorized as get_stock_news_categorized_service
from app.services.stock.basic_info import get_basic_info as get_basic_info_service
from app.services.stock.financials import get_financial as get_financial_service, get_financial_metrics as get_financial_metrics_service
from app.services.stock.intraday import get_intraday as get_intraday_service
from app.services.stock.kline import get_kline as get_stock_kline_service
from app.services.screener.percentiles import compute_percentile
from app.services.stock.search import search_stocks as search_stock_items
from app.services.stock.valuation import get_valuation as get_valuation_service, get_valuation_detail as get_valuation_detail_service
from app.services.stock.retail import (
    get_retail_sentiment as get_retail_sentiment_service,
    get_stock_sentiment as get_stock_sentiment_service,
)
from app.services.market.dragon_tiger import get_dragon_tiger_detail as get_dragon_tiger_detail_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_model=list[StockSearchItem])
async def search_stocks(q: str = Query(..., min_length=1, description="股票名称或代码")):
    """按名称或代码模糊搜索股票。

    Param:
        q: 查询关键字（查询参数），可为代码片段或股票名称，至少 1 个字符。
    Return:
        list[StockSearchItem]: 匹配到的股票候选条目。
    """
    async def execute():
        result = await search_stock_items(q)
        logger.info("搜索结果: q=%s, 匹配%d条", q, len(result))
        return result
    return await run_endpoint("搜索股票", execute)


@router.get("/{code}/info", response_model=StockBasicInfo)
async def get_stock_info(code: str):
    """获取个股基本资料。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        StockBasicInfo: 公司名称、所属行业、上市信息等基础数据。
    """
    return await run_endpoint("获取股票信息", lambda: get_basic_info_service(code))


@router.get("/{code}/kline", response_model=KlineData)
async def get_kline(
    code: str,
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    adjust: str = Query("qfq", pattern="^(qfq|hfq|)$"),
):
    """获取个股 K 线数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
        period: K 线周期（查询参数），daily / weekly / monthly。
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空。
        adjust: 复权类型（查询参数），qfq、hfq 或空字符串表示不复权。
    Return:
        KlineData: 按时间排序的 K 线条目集合。
    """
    return await run_endpoint("获取K线", lambda: get_stock_kline_service(code, period, start_date, end_date, adjust))


@router.get("/{code}/financial")
async def get_financial(code: str, type: str = Query("balance", pattern="^(balance|profit|cashflow)$")):
    """获取个股财务报表数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
        type: 报表类型（查询参数），balance / profit / cashflow。
    Return:
        dict: 对应报表的多期数据。
    """
    return await run_endpoint("获取财务数据", lambda: get_financial_service(code, type))


@router.get("/{code}/intraday", response_model=IntradayData)
async def get_intraday(code: str):
    """获取个股分时数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        IntradayData: 当日分时价、量、均价等序列。
    """
    return await run_endpoint("获取分时数据", lambda: get_intraday_service(code))


@router.get("/{code}/financial-metrics", response_model=FinancialMetrics)
async def get_financial_metrics(code: str):
    """获取个股关键财务指标汇总。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        FinancialMetrics: 营收、利润、ROE 等核心财务指标。
    """
    return await run_endpoint("获取财务指标", lambda: get_financial_metrics_service(code))


@router.get("/{code}/valuation")
async def get_valuation(code: str):
    """获取个股估值数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: PE、PB、市值等估值指标。
    """
    return await run_endpoint("获取估值数据", lambda: get_valuation_service(code))


@router.get("/{code}/valuation-detail", response_model=ValuationDetail)
async def get_valuation_detail(code: str):
    """获取个股估值详情，包括历史分位与对比指标。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        ValuationDetail: 当前估值、历史分位以及相关明细。
    """
    return await run_endpoint("获取估值详情", lambda: get_valuation_detail_service(code, compute_percentile))


@router.get("/{code}/news")
async def get_news(code: str):
    """获取个股最新新闻流。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[dict] | dict: 按时间排序的新闻条目集合。
    """
    return await run_endpoint("获取新闻", lambda: get_stock_news_service(code))


@router.get("/{code}/indicators")
async def get_indicators(code: str):
    """基于日 K 线计算个股常用技术指标。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 包含 RSI、MACD、KDJ 等技术指标的字典。
    """
    async def execute():
        kline = await get_stock_kline_service(code)
        indicators = technical.calculate_all(kline.items)
        logger.info("技术指标计算完成: code=%s, 数据点=%d", code, len(kline.items))
        return indicators
    return await run_endpoint("计算技术指标", execute)


@router.get("/{code}/sentiment")
async def get_sentiment(code: str):
    """获取个股情绪数据（热度排名、热度评分、新闻数量）。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 个股情绪指标。
    """
    return await run_endpoint("获取情绪数据", lambda: get_stock_sentiment_service(code))


@router.get("/{code}/retail-sentiment")
async def get_retail_sentiment(code: str):
    """获取个股散户情绪指标（股吧帖子情绪分析）。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 散户情绪相关指标与详情。
    """
    return await run_endpoint("获取散户情绪数据", lambda: get_retail_sentiment_service(code))


@router.get("/{code}/news-categorized")
async def get_news_categorized(code: str):
    """获取按类别分组的个股新闻流。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 按公告、新闻、研报等类别整理的新闻条目。
    """
    return await run_endpoint("获取分类新闻数据", lambda: get_stock_news_categorized_service(code))


@router.get("/{code}/dragon-tiger")
async def get_dragon_tiger_detail(code: str, report_date: str = Query(..., description="报告日期 YYYY-MM-DD")):
    """获取指定龙虎榜个股的买卖席位明细。

    Param:
        code: 股票代码（路径参数）。
        report_date: 报告日期（查询参数），格式 YYYY-MM-DD。
    Return:
        dict: 买入卖出席位明细及净额。
    """
    return await run_endpoint("获取龙虎榜明细", lambda: get_dragon_tiger_detail_service(code, report_date))
