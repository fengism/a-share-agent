"""Portfolio API 与领域数据模型。"""

from datetime import datetime
from typing import Literal

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


class PortfolioTransactionCreate(BaseModel):
    stock_code: str
    side: Literal["buy", "sell"]
    trade_price: float = Field(gt=0, le=1_000_000)
    trade_time: datetime
    shares: int = Field(gt=0, le=1_000_000_000)
    fee: float = Field(default=0, ge=0, le=1_000_000_000)
    note: str = Field(default="", max_length=500)

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, value: str) -> str:
        return normalize_code(value).raw

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class PortfolioAccountSettingsUpdate(BaseModel):
    initial_cash: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    max_total_position_pct: float = Field(default=80, gt=0, le=100)
    max_single_stock_pct: float = Field(default=30, gt=0, le=100)
    max_sector_pct: float = Field(default=40, gt=0, le=100)


class PortfolioAccountSettings(PortfolioAccountSettingsUpdate):
    updated_at: str | None = None


class PortfolioLotMatch(BaseModel):
    buy_transaction_id: int
    buy_time: str
    buy_price: float
    shares: int
    unit_cost: float
    matched_cost: float


class PortfolioTransaction(BaseModel):
    id: int
    stock_code: str
    stock_name: str
    side: Literal["buy", "sell"]
    trade_price: float
    trade_time: str
    shares: int
    fee: float
    note: str
    created_at: str
    matched_cost: float | None = None
    realized_profit_amount: float | None = None
    matches: list[PortfolioLotMatch] = Field(default_factory=list)


class PortfolioTransactionPreview(BaseModel):
    stock_code: str
    side: Literal["buy", "sell"]
    trade_time: str
    available_shares: int
    shares_after_trade: int
    current_shares_after: int
    matched_cost: float | None = None
    realized_profit_amount: float | None = None
    matches: list[PortfolioLotMatch] = Field(default_factory=list)
    trade_amount: float
    fee: float
    cash_balance_after: float | None = None
    estimated_total_assets_after: float | None = None
    total_position_pct_after: float | None = None
    stock_position_pct_after: float | None = None
    sector_name: str | None = None
    sector_position_pct_after: float | None = None
    warnings: list[str] = Field(default_factory=list)


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
    realized_profit_amount: float
    total_profit_amount: float | None = None
    allocation_pct: float | None = None
    securities_allocation_pct: float | None = None
    sector_name: str | None = None
    profit_contribution_pct: float | None = None


class PortfolioSummary(BaseModel):
    stock_count: int
    position_count: int
    transaction_count: int
    total_cost: float
    priced_cost: float
    total_market_value: float
    total_profit_amount: float
    total_profit_pct: float | None = None
    unrealized_profit_amount: float
    realized_profit_amount: float
    combined_profit_amount: float
    profitable_count: int
    losing_count: int
    unpriced_count: int
    cash_configured: bool
    initial_cash: float | None = None
    cash_balance: float | None = None
    estimated_securities_value: float
    total_asset_value: float | None = None
    total_position_pct: float | None = None


class PortfolioClosedPosition(BaseModel):
    stock_code: str
    stock_name: str
    transaction_count: int
    buy_count: int
    sell_count: int
    total_shares: int
    matched_cost: float
    realized_profit_amount: float
    realized_profit_pct: float | None = None
    first_trade_time: str
    last_trade_time: str
    holding_days: int


class PortfolioRiskSummary(BaseModel):
    largest_position_stock_code: str | None = None
    largest_position_stock_name: str | None = None
    max_single_stock_pct: float | None = None
    top3_concentration_pct: float | None = None
    concentration_level: Literal["low", "medium", "high", "unknown"]
    priced_stock_count: int
    unpriced_stock_count: int
    max_total_position_limit_pct: float
    max_single_stock_limit_pct: float
    max_sector_limit_pct: float
    largest_sector_name: str | None = None
    largest_sector_pct: float | None = None
    sector_allocations: list["PortfolioSectorAllocation"] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PortfolioSectorAllocation(BaseModel):
    sector_name: str
    market_value: float
    allocation_pct: float | None = None
    stock_codes: list[str] = Field(default_factory=list)


class PortfolioResponse(BaseModel):
    positions: list[PortfolioPosition]
    stocks: list[PortfolioStockSummary]
    transactions: list[PortfolioTransaction]
    closed_positions: list[PortfolioClosedPosition]
    summary: PortfolioSummary
    risk: PortfolioRiskSummary
    settings: PortfolioAccountSettings
    quoted_at: str
    quote_source: str = "tencent"
    quote_stale: bool = False
