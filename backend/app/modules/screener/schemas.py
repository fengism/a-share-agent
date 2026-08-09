from pydantic import BaseModel, Field

from app.contracts.stock import StockConcept


class ScreenerFilter(BaseModel):
    """Purpose: 股票筛选接口的过滤条件参数。"""
    pe_min: float | None = None
    pe_max: float | None = None
    pb_min: float | None = None
    pb_max: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    market_cap_min: float | None = None  # 亿元
    market_cap_max: float | None = None
    change_pct_min: float | None = None
    change_pct_max: float | None = None
    turnover_pct_min: float | None = None
    turnover_pct_max: float | None = None
    industries: list[str] | None = None
    sort_by: str = "market_cap"
    sort_order: str = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class ScreenerItem(BaseModel):
    """Purpose: 股票筛选结果中的单只股票信息。"""
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None  # 亿元
    turnover_pct: float | None = None
    volume: float | None = None
    second_industry: StockConcept | None = None


class ScreenerResult(BaseModel):
    """Purpose: 股票筛选的分页结果。"""
    items: list[ScreenerItem]
    total: int
    page: int
    page_size: int


class ValuationPercentileRequest(BaseModel):
    """Purpose: 估值百分位查询接口的请求参数。"""
    codes: list[str]
    period: str = "近三年"
    indicator: str = "市盈率(TTM)"


class ValuationPercentileItem(BaseModel):
    """Purpose: 单只股票的估值百分位结果。"""
    code: str
    percentile: float | None = None


class ValuationPercentileResult(BaseModel):
    """Purpose: 估值百分位批量查询的返回结果。"""
    items: list[ValuationPercentileItem]
