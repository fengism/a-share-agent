"""个股分析 HTTP 请求与响应模型。"""

from pydantic import BaseModel

from app.contracts.market import KlineData
from app.market_data.stock.public import IntradayData, StockBasicInfo, StockValuation
from app.modules.analysis.events import AnalysisProgress, AnalysisStage
from app.modules.analysis.models import AnalysisResult, FactorAnalysis

__all__ = [
    "AnalysisHistoryItem",
    "AnalysisPageData",
    "AnalysisProgress",
    "AnalysisResult",
    "AnalysisStage",
    "FactorAnalysis",
]


class AnalysisHistoryItem(BaseModel):
    """Purpose: 分析历史列表中单条记录的摘要信息。"""
    stock_code: str
    stock_name: str
    analysis_date: str
    current_price: float | None = None
    overall_rating: int | None = None
    signal: str | None = None
    confidence: float | None = None
    can_delete: bool


class AnalysisPageData(BaseModel):
    stock_info: StockBasicInfo | None = None
    kline: KlineData | None = None
    intraday: IntradayData | None = None
    valuation: StockValuation | None = None
    cached_analysis: AnalysisResult | None = None
