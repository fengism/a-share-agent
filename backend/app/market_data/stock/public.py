"""Stable stock-data capabilities for product modules and Agent tools."""

from app.market_data.stock.classification.service import (
    build_industry_mapping,
    fetch_industry_mapping_sw_second,
    get_industry_list,
    get_industry_mapping,
    update_industry_mapping_sw_second_file,
)
from app.market_data.stock.fundamentals.financials import get_financial, get_financial_metrics
from app.market_data.stock.fundamentals.schemas import (
    FinancialMetrics,
    FinancialStatementRow,
    StockCompareItem,
)
from app.market_data.stock.insights.fund_flow import get_stock_fund_flow
from app.market_data.stock.insights.news import get_stock_news, get_stock_news_categorized
from app.market_data.stock.insights.retail import get_retail_sentiment, get_stock_sentiment
from app.market_data.stock.insights.risk import get_stock_risk_data
from app.market_data.stock.insights.schemas import RetailSentiment, StockFundFlowItem, StockSentiment
from app.market_data.stock.profile.basic_info import get_basic_info
from app.market_data.stock.profile.name_map import build_stock_name_map, get_stock_name_map
from app.market_data.stock.profile.schemas import StockBasicInfo
from app.market_data.stock.profile.search import search_stocks
from app.market_data.stock.quotes import technical
from app.market_data.stock.quotes.historical import (
    HistoricalBarSet,
    get_historical_bars,
    historical_bar_hash,
)
from app.market_data.stock.quotes.intraday import get_intraday
from app.market_data.stock.quotes.kline import get_kline
from app.market_data.stock.quotes.realtime import fetch_realtime_quotes
from app.market_data.stock.quotes.schemas import IntradayData
from app.market_data.stock.quotes.spot_snapshot import get_spot_snapshot
from app.market_data.stock.quotes.technical_schemas import TechnicalIndicators
from app.market_data.stock.valuation.detail import get_valuation_detail
from app.market_data.stock.valuation.orchestrator import get_valuation
from app.market_data.stock.valuation.percentiles import compute_percentile, compute_percentiles
from app.market_data.stock.valuation.schemas import StockValuation, ValuationDetail

__all__ = [
    "build_stock_name_map",
    "build_industry_mapping",
    "compute_percentile",
    "compute_percentiles",
    "FinancialMetrics",
    "FinancialStatementRow",
    "fetch_realtime_quotes",
    "fetch_industry_mapping_sw_second",
    "get_basic_info",
    "get_financial",
    "get_financial_metrics",
    "get_historical_bars",
    "historical_bar_hash",
    "get_intraday",
    "get_industry_list",
    "get_industry_mapping",
    "get_kline",
    "get_retail_sentiment",
    "get_stock_fund_flow",
    "get_stock_name_map",
    "get_stock_news",
    "get_stock_news_categorized",
    "get_stock_risk_data",
    "get_spot_snapshot",
    "get_stock_sentiment",
    "get_valuation",
    "get_valuation_detail",
    "IntradayData",
    "HistoricalBarSet",
    "RetailSentiment",
    "search_stocks",
    "StockBasicInfo",
    "StockCompareItem",
    "StockFundFlowItem",
    "StockSentiment",
    "StockValuation",
    "technical",
    "TechnicalIndicators",
    "update_industry_mapping_sw_second_file",
    "ValuationDetail",
]
