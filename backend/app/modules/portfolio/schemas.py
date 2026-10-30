"""Portfolio API 与领域数据模型。"""

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.market import normalize_code
from app.financial_data.hk.service import normalize_hk_code

_HK_CODE_PATTERN = re.compile(r"^(?:hk)?(\d{1,5})$", re.IGNORECASE)


def is_hk_stock_code(code: str) -> bool:
    cleaned = str(code or "").strip()
    if cleaned.upper().endswith(".HK"):
        cleaned = cleaned[:-3].strip()
    return bool(_HK_CODE_PATTERN.fullmatch(cleaned))


def normalize_portfolio_stock_code(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned.upper().endswith(".HK"):
        cleaned = cleaned[:-3].strip()
    if is_hk_stock_code(cleaned):
        return normalize_hk_code(cleaned)
    return normalize_code(cleaned).raw


class PortfolioPositionCreate(BaseModel):
    stock_code: str
    buy_price: float = Field(gt=0, le=1_000_000)
    buy_time: datetime
    shares: int = Field(gt=0, le=1_000_000_000)

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, value: str) -> str:
        return normalize_portfolio_stock_code(value)


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
        return normalize_portfolio_stock_code(value)

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
    currency: str = "CNY"


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
    currency: str = "CNY"
    fx_rate_to_cny: float = 1.0
    trade_amount: float = 0
    trade_amount_native: float = 0
    fee_native: float = 0
    matched_cost: float | None = None
    realized_profit_amount: float | None = None
    matches: list[PortfolioLotMatch] = Field(default_factory=list)


class PortfolioTransactionPreview(BaseModel):
    stock_code: str
    side: Literal["buy", "sell"]
    trade_time: str
    currency: str = "CNY"
    fx_rate_to_cny: float = 1.0
    available_shares: int
    # available_shares 是交易时点的全部持仓；sellable_shares 扣除了 A 股当日买入冻结部分。
    sellable_shares: int | None = None
    frozen_shares: int | None = None
    sellable_after_trade: int | None = None
    shares_after_trade: int
    current_shares_after: int
    matched_cost: float | None = None
    realized_profit_amount: float | None = None
    matches: list[PortfolioLotMatch] = Field(default_factory=list)
    trade_amount: float
    trade_amount_native: float = 0
    fee: float
    fee_native: float = 0
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
    currency: str = "CNY"
    fx_rate_to_cny: float = 1.0
    current_price: float | None = None
    change_pct: float | None = None
    prev_close: float | None = None
    daily_profit_amount: float | None = None
    daily_profit_pct: float | None = None
    sellable_shares: int | None = None
    frozen_shares: int | None = None
    cost_value: float
    cost_value_native: float = 0
    market_value: float | None = None
    profit_amount: float | None = None
    profit_pct: float | None = None


class PortfolioStockSummary(BaseModel):
    stock_code: str
    stock_name: str
    position_count: int
    total_shares: int
    average_cost: float
    currency: str = "CNY"
    fx_rate_to_cny: float = 1.0
    current_price: float | None = None
    change_pct: float | None = None
    prev_close: float | None = None
    daily_profit_amount: float | None = None
    daily_profit_pct: float | None = None
    sellable_shares: int | None = None
    frozen_shares: int | None = None
    lot_size: int | None = None
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
    max_additional_value: float | None = None
    max_additional_shares: int | None = None


class PortfolioSummary(BaseModel):
    stock_count: int
    position_count: int
    transaction_count: int
    base_currency: str = "CNY"
    fx_rates: dict[str, float] = Field(default_factory=dict)
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
    previous_close_value: float = 0
    daily_profit_amount: float = 0
    daily_profit_pct: float | None = None


class PortfolioEquityCurvePoint(BaseModel):
    date: date
    cash_balance: float | None = None
    securities_value: float
    total_assets: float | None = None
    cumulative_return_pct: float | None = None
    drawdown_pct: float | None = None
    unpriced_count: int = Field(default=0, ge=0)


class PortfolioEquityCurveResponse(BaseModel):
    mode: Literal["total_assets", "securities_only"]
    start_date: date | None = None
    end_date: date
    base_currency: str = "CNY"
    fx_rates: dict[str, float] = Field(default_factory=dict)
    initial_cash: float | None = None
    current_total_assets: float | None = None
    current_securities_value: float | None = None
    total_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    annualized_return_pct: float | None = None
    annualized_volatility_pct: float | None = None
    sharpe_ratio: float | None = None
    calmar_ratio: float | None = None
    win_rate_pct: float | None = None
    best_day_pct: float | None = None
    worst_day_pct: float | None = None
    longest_drawdown_days: int | None = None
    trading_days: int = 0
    risk_free_rate_pct: float = 0.0
    points: list[PortfolioEquityCurvePoint] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PortfolioClosedPosition(BaseModel):
    stock_code: str
    stock_name: str
    currency: str = "CNY"
    fx_rate_to_cny: float = 1.0
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


class PortfolioTrimSuggestion(BaseModel):
    """超限仓位的减仓建议（按最小交易单位向上取整，确保回到上限内）。"""

    stock_code: str
    stock_name: str
    sector_name: str | None = None
    current_pct: float
    target_pct: float
    suggested_shares: int
    sellable_shares: int
    estimated_amount: float
    lot_size: int
    reasons: list[str] = Field(default_factory=list)


class PortfolioRiskSummary(BaseModel):
    largest_position_stock_code: str | None = None
    largest_position_stock_name: str | None = None
    max_single_stock_pct: float | None = None
    top3_concentration_pct: float | None = None
    top5_concentration_pct: float | None = None
    # 组合级剩余可加仓金额（人民币）：同时受总仓位上限和可用现金约束，未扣交易费用。
    remaining_add_capacity: float | None = None
    concentration_index: float | None = None
    effective_holding_count: float | None = None
    # 以下三项按证券市值内部权重计算，不含现金，和含现金口径分开展示。
    securities_top5_concentration_pct: float | None = None
    securities_concentration_index: float | None = None
    securities_effective_holding_count: float | None = None
    cash_pct: float | None = None
    concentration_level: Literal["low", "medium", "high", "unknown"]
    priced_stock_count: int
    unpriced_stock_count: int
    max_total_position_limit_pct: float
    max_single_stock_limit_pct: float
    max_sector_limit_pct: float
    largest_sector_name: str | None = None
    largest_sector_pct: float | None = None
    sector_allocations: list["PortfolioSectorAllocation"] = Field(default_factory=list)
    trim_suggestions: list[PortfolioTrimSuggestion] = Field(default_factory=list)
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
