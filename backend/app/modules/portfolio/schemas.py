"""Portfolio API 与领域数据模型。"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.market import normalize_code


class PortfolioPositionCreate(BaseModel):
    stock_code: str
    buy_price: float = Field(gt=0, le=1_000_000)
    buy_time: datetime
    shares: int = Field(gt=0, le=1_000_000_000)

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, value: str) -> str:
        return normalize_code(value).raw


class PortfolioPosition(BaseModel):
    id: int
    stock_code: str
    stock_name: str
    buy_price: float
    buy_time: str
    shares: int
    current_price: float | None = None
    change_pct: float | None = None
    cost_value: float
    market_value: float | None = None
    profit_amount: float | None = None
    profit_pct: float | None = None


class PortfolioStockSummary(BaseModel):
    stock_code: str
    stock_name: str
    position_count: int
    total_shares: int
    average_cost: float
    current_price: float | None = None
    change_pct: float | None = None
    cost_value: float
    market_value: float | None = None
    profit_amount: float | None = None
    profit_pct: float | None = None


class PortfolioSummary(BaseModel):
    stock_count: int
    position_count: int
    total_cost: float
    priced_cost: float
    total_market_value: float
    total_profit_amount: float
    total_profit_pct: float | None = None
    profitable_count: int
    losing_count: int
    unpriced_count: int


class PortfolioResponse(BaseModel):
    positions: list[PortfolioPosition]
    stocks: list[PortfolioStockSummary]
    summary: PortfolioSummary
    quoted_at: str
    quote_source: str = "tencent"
    quote_stale: bool = False


class PortfolioDeleteResponse(BaseModel):
    deleted: bool
