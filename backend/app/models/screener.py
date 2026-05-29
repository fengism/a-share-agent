from pydantic import BaseModel, Field

from app.models.stock import StockConcept


class ScreenerFilter(BaseModel):
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
    items: list[ScreenerItem]
    total: int
    page: int
    page_size: int


class ValuationPercentileRequest(BaseModel):
    codes: list[str]
    period: str = "近三年"
    indicator: str = "市盈率(TTM)"


class ValuationPercentileItem(BaseModel):
    code: str
    percentile: float | None = None


class ValuationPercentileResult(BaseModel):
    items: list[ValuationPercentileItem]
