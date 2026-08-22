"""个股资讯、情绪与资金洞察 HTTP API。"""

from fastapi import APIRouter, Query

from app.domain.news import CategorizedStockNews, NewsSearchItem
from app.financial_data.market.public import DragonTigerDetail
from app.financial_data.market.public import get_dragon_tiger_detail as get_dragon_tiger_detail_service
from app.financial_data.stock.public import RetailSentiment, StockFundFlowItem, StockSentiment
from app.financial_data.stock.public import get_retail_sentiment as get_retail_sentiment_service
from app.financial_data.stock.public import get_stock_fund_flow as get_stock_fund_flow_service
from app.financial_data.stock.public import get_stock_news as get_stock_news_service
from app.financial_data.stock.public import get_stock_news_categorized as get_stock_news_categorized_service
from app.financial_data.stock.public import get_stock_sentiment as get_stock_sentiment_service

router = APIRouter()


@router.get("/{code}/news", response_model=list[NewsSearchItem])
async def get_news(code: str):
    """获取个股最新新闻流。"""
    return await get_stock_news_service(code)


@router.get("/{code}/sentiment", response_model=StockSentiment)
async def get_sentiment(code: str):
    """获取个股情绪数据。"""
    return await get_stock_sentiment_service(code)


@router.get("/{code}/retail-sentiment", response_model=RetailSentiment)
async def get_retail_sentiment(code: str):
    """获取个股散户情绪指标。"""
    return await get_retail_sentiment_service(code)


@router.get("/{code}/fund-flow", response_model=list[StockFundFlowItem])
async def get_fund_flow(code: str):
    """获取个股资金流向日级数据。"""
    return await get_stock_fund_flow_service(code)


@router.get("/{code}/news-categorized", response_model=CategorizedStockNews)
async def get_news_categorized(code: str):
    """获取按类别分组的个股新闻流。"""
    return await get_stock_news_categorized_service(code)


@router.get("/{code}/dragon-tiger", response_model=list[DragonTigerDetail])
async def get_dragon_tiger_detail(
    code: str,
    report_date: str = Query(..., description="报告日期 YYYY-MM-DD"),
):
    """获取指定龙虎榜个股的买卖席位明细。"""
    return await get_dragon_tiger_detail_service(code, report_date)
