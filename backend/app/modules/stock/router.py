"""个股产品 API。"""

import logging

from fastapi import APIRouter, Query

from app.contracts.market import KlineData
from app.contracts.search import CategorizedStockNews, NewsSearchItem
from app.contracts.stock import StockSearchItem
from app.market_data.market.public import DragonTigerDetail
from app.market_data.market.public import get_dragon_tiger_detail as get_dragon_tiger_detail_service
from app.market_data.stock.public import (
    FinancialMetrics,
    FinancialStatementRow,
    IntradayData,
    RetailSentiment,
    StockBasicInfo,
    StockCompareItem,
    StockFundFlowItem,
    StockSentiment,
    StockValuation,
    TechnicalIndicators,
    ValuationDetail,
    compute_percentile,
    technical,
)
from app.market_data.stock.public import get_basic_info as get_basic_info_service
from app.market_data.stock.public import get_financial as get_financial_service
from app.market_data.stock.public import get_financial_metrics as get_financial_metrics_service
from app.market_data.stock.public import get_intraday as get_intraday_service
from app.market_data.stock.public import get_kline as get_stock_kline_service
from app.market_data.stock.public import get_retail_sentiment as get_retail_sentiment_service
from app.market_data.stock.public import get_stock_fund_flow as get_stock_fund_flow_service
from app.market_data.stock.public import get_stock_news as get_stock_news_service
from app.market_data.stock.public import get_stock_news_categorized as get_stock_news_categorized_service
from app.market_data.stock.public import get_stock_sentiment as get_stock_sentiment_service
from app.market_data.stock.public import get_valuation as get_valuation_service
from app.market_data.stock.public import get_valuation_detail as get_valuation_detail_service
from app.market_data.stock.public import search_stocks as search_stock_items
from app.modules.stock.compare import compare_stocks as compare_stocks_service

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

    result = await search_stock_items(q)
    logger.info("搜索结果: q=%s, 匹配%d条", q, len(result))
    return result


@router.get("/{code}/info", response_model=StockBasicInfo)
async def get_stock_info(code: str):
    """获取个股基本资料。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        StockBasicInfo: 公司名称、所属行业、上市信息等基础数据。
    """
    return await get_basic_info_service(code)


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
    return await get_stock_kline_service(code, period, start_date, end_date, adjust)


@router.get("/{code}/intraday", response_model=IntradayData)
async def get_intraday(code: str):
    """获取个股分时数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        IntradayData: 当日分时价、量、均价等序列。
    """
    return await get_intraday_service(code)


@router.get("/{code}/indicators", response_model=TechnicalIndicators)
async def get_indicators(code: str):
    """基于日 K 线计算个股常用技术指标。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 包含 RSI、MACD、KDJ 等技术指标的字典。
    """

    kline = await get_stock_kline_service(code)
    indicators = technical.calculate_all(kline.items)
    logger.info("技术指标计算完成: code=%s, 数据点=%d", code, len(kline.items))
    return indicators


@router.get("/{code}/financial", response_model=list[FinancialStatementRow])
async def get_financial(code: str, type: str = Query("balance", pattern="^(balance|profit|cashflow)$")):
    """获取个股财务报表数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
        type: 报表类型（查询参数），balance / profit / cashflow。
    Return:
        dict: 对应报表的多期数据。
    """
    return await get_financial_service(code, type)


@router.get("/{code}/financial-metrics", response_model=FinancialMetrics)
async def get_financial_metrics(code: str):
    """获取个股关键财务指标汇总。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        FinancialMetrics: 营收、利润、ROE 等核心财务指标。
    """
    return await get_financial_metrics_service(code)


@router.get("/{code}/valuation", response_model=StockValuation)
async def get_valuation(code: str):
    """获取个股估值数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: PE、PB、市值等估值指标。
    """
    return await get_valuation_service(code)


@router.get("/{code}/valuation-detail", response_model=ValuationDetail)
async def get_valuation_detail(code: str):
    """获取个股估值详情，包括历史分位与对比指标。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        ValuationDetail: 当前估值、历史分位以及相关明细。
    """
    return await get_valuation_detail_service(code, compute_percentile)


@router.get("/compare", response_model=list[StockCompareItem], response_model_exclude_unset=True)
async def get_compare(codes: str = Query(..., description="逗号分隔的股票代码，如 600519,000858")):
    """多股对比分析，获取基本信息、估值和财务指标进行横向对比。

    Param:
        codes: 逗号分隔的股票代码（查询参数），最多 5 个。
    Return:
        list[dict]: 每只股票的合并数据列表。
    """
    return await compare_stocks_service(codes)


@router.get("/{code}/news", response_model=list[NewsSearchItem])
async def get_news(code: str):
    """获取个股最新新闻流。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[dict] | dict: 按时间排序的新闻条目集合。
    """
    return await get_stock_news_service(code)


@router.get("/{code}/sentiment", response_model=StockSentiment)
async def get_sentiment(code: str):
    """获取个股情绪数据（热度排名、热度评分、新闻数量）。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 个股情绪指标。
    """
    return await get_stock_sentiment_service(code)


@router.get("/{code}/retail-sentiment", response_model=RetailSentiment)
async def get_retail_sentiment(code: str):
    """获取个股散户情绪指标（股吧帖子情绪分析）。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 散户情绪相关指标与详情。
    """
    return await get_retail_sentiment_service(code)


@router.get("/{code}/fund-flow", response_model=list[StockFundFlowItem])
async def get_fund_flow(code: str):
    """获取个股资金流向日级数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[dict]: 按日期倒序排列的资金流向列表。
    """
    return await get_stock_fund_flow_service(code)


@router.get("/{code}/news-categorized", response_model=CategorizedStockNews)
async def get_news_categorized(code: str):
    """获取按类别分组的个股新闻流。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 按公告、新闻、研报等类别整理的新闻条目。
    """
    return await get_stock_news_categorized_service(code)


@router.get("/{code}/dragon-tiger", response_model=list[DragonTigerDetail])
async def get_dragon_tiger_detail(code: str, report_date: str = Query(..., description="报告日期 YYYY-MM-DD")):
    """获取指定龙虎榜个股的买卖席位明细。

    Param:
        code: 股票代码（路径参数）。
        report_date: 报告日期（查询参数），格式 YYYY-MM-DD。
    Return:
        dict: 买入卖出席位明细及净额。
    """
    return await get_dragon_tiger_detail_service(code, report_date)
