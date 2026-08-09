"""量化策略、回测请求与结果协议。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuantStrategyType = Literal["ma_cross", "momentum_breakout", "rsi_reversion"]
QuantRunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class QuantStrategyConfig(BaseModel):
    type: QuantStrategyType = "ma_cross"
    fast_period: int = Field(default=5, ge=2, le=120)
    slow_period: int = Field(default=20, ge=3, le=250)
    lookback_period: int = Field(default=20, ge=2, le=250)
    rsi_period: int = Field(default=14, ge=2, le=100)
    buy_threshold: float = Field(default=30, ge=0, le=100)
    sell_threshold: float = Field(default=70, ge=0, le=100)

    @model_validator(mode="after")
    def validate_strategy(self):
        if self.fast_period >= self.slow_period:
            raise ValueError("短周期必须小于长周期")
        if self.buy_threshold >= self.sell_threshold:
            raise ValueError("买入阈值必须小于卖出阈值")
        return self


class QuantUniverse(BaseModel):
    source: Literal["custom", "portfolio"] = "custom"
    codes: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_codes(self):
        normalized = list(dict.fromkeys(code.strip() for code in self.codes if code.strip()))
        if self.source == "custom" and not normalized:
            raise ValueError("自定义股票池不能为空")
        self.codes = normalized
        return self


class QuantExecutionConfig(BaseModel):
    initial_cash: float = Field(default=1_000_000, gt=0, le=1_000_000_000)
    commission_rate: float = Field(default=0.0003, ge=0, le=0.01)
    minimum_commission: float = Field(default=5, ge=0, le=1000)
    stamp_duty_rate: float = Field(default=0.0005, ge=0, le=0.01)
    transfer_fee_rate: float = Field(default=0.00001, ge=0, le=0.01)
    slippage_bps: float = Field(default=5, ge=0, le=500)
    lot_size: int = Field(default=100, ge=1, le=10_000)
    risk_free_rate: float = Field(default=0.015, ge=-0.1, le=0.5)


class QuantBacktestCreate(BaseModel):
    name: str = Field(default="未命名回测", min_length=1, max_length=80)
    universe: QuantUniverse
    strategy: QuantStrategyConfig = Field(default_factory=QuantStrategyConfig)
    execution: QuantExecutionConfig = Field(default_factory=QuantExecutionConfig)
    start_date: date
    end_date: date
    benchmark: str = Field(default="000300", min_length=6, max_length=8)

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_date >= self.end_date:
            raise ValueError("开始日期必须早于结束日期")
        if (self.end_date - self.start_date).days > 5 * 366:
            raise ValueError("回测周期不能超过 5 年")
        return self


class QuantEquityPoint(BaseModel):
    date: str
    equity: float
    benchmark: float | None = None
    drawdown: float


class QuantMonthlyReturn(BaseModel):
    month: str
    return_pct: float


class QuantTrade(BaseModel):
    date: str
    code: str
    side: Literal["buy", "sell"]
    price: float
    shares: int
    amount: float
    fee: float
    realized_pnl: float | None = None


class QuantMetrics(BaseModel):
    total_return: float
    annualized_return: float
    benchmark_return: float | None = None
    excess_return: float | None = None
    annualized_volatility: float
    sharpe_ratio: float | None = None
    max_drawdown: float
    win_rate: float | None = None
    profit_loss_ratio: float | None = None
    turnover_rate: float
    trade_count: int


class QuantBacktestResult(BaseModel):
    engine_version: str
    data_hash: str
    data_sources: list[str]
    codes: list[str]
    metrics: QuantMetrics
    equity_curve: list[QuantEquityPoint]
    monthly_returns: list[QuantMonthlyReturn]
    trades: list[QuantTrade]


class QuantBacktestRun(BaseModel):
    id: str
    name: str
    status: QuantRunStatus
    request: QuantBacktestCreate
    result: QuantBacktestResult | None = None
    error: str | None = None
    attempts: int = 0
    created_at: float
    updated_at: float
    completed_at: float | None = None


class QuantBacktestList(BaseModel):
    items: list[QuantBacktestRun]


class QuantStrategyPreset(BaseModel):
    key: QuantStrategyType
    name: str
    description: str
    config: QuantStrategyConfig


class QuantStrategySave(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    config: QuantStrategyConfig


class QuantSavedStrategy(BaseModel):
    id: int
    name: str
    config: QuantStrategyConfig
    created_at: float
    updated_at: float


class QuantDeleteResponse(BaseModel):
    deleted: bool
