"""个股资讯、情绪与资金洞察 HTTP API。"""

from fastapi import APIRouter, Query

from app.domain.news import CategorizedStockNews, NewsSearchItem
from app.financial_data.market.public import DragonTigerDetail
from app.financial_data.market.public import get_dragon_tiger_detail as get_dragon_tiger_detail_service
from app.financial_data.stock.public import (
    RetailSentiment,
    StockBulletinPage,
    StockFundFlowItem,
    StockFundFlowPage,
    StockReportPage,
    StockSentiment,
)
from app.financial_data.stock.public import get_retail_sentiment as get_retail_sentiment_service
from app.financial_data.stock.public import get_stock_bulletins as get_stock_bulletins_service
from app.financial_data.stock.public import get_stock_fund_flow as get_stock_fund_flow_service
from app.financial_data.stock.public import get_stock_fund_flow_page as get_stock_fund_flow_page_service
from app.financial_data.stock.public import get_stock_news as get_stock_news_service
from app.financial_data.stock.public import get_stock_news_categorized as get_stock_news_categorized_service
from app.financial_data.stock.public import get_stock_reports as get_stock_reports_service
from app.financial_data.stock.public import get_stock_sentiment as get_stock_sentiment_service

router = APIRouter()


@router.get("/{code}/news", response_model=list[NewsSearchItem])
async def get_news(code: str):
    """获取个股最新新闻流。"""
    return await get_stock_news_service(code)


@router.get("/{code}/bulletins", response_model=StockBulletinPage)
async def get_bulletins(
    code: str,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=30, description="每页条数"),
):
    """获取个股公司公告分页列表（新浪财经）。"""
    return await get_stock_bulletins_service(code, page=page, page_size=page_size)


@router.get("/{code}/reports", response_model=StockReportPage)
async def get_reports(
    code: str,
    months: int = Query(6, ge=1, le=24, description="回溯月数，默认最近 6 个月"),
):
    """获取个股券商研报评级列表（新浪财经，最近 N 个月）。"""
    return await get_stock_reports_service(code, months=months)


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


@router.get("/{code}/fund-flow-pages", response_model=StockFundFlowPage)
async def get_fund_flow_page(code: str, cursor: str | None = Query(None, max_length=80)):
    """每批最多 20 日，后续批次固定首批来源和日期。"""
    return await get_stock_fund_flow_page_service(code, cursor)


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
