"""量化策略、回测请求与结果协议。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.market import KlineItem
from app.modules.quant.strategies.contracts import (
    ComparisonOperator,
    ParameterValue,
    SignalOperand,
    StrategyDefinition,
    StrategySnapshot,
)

QuantRunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]

_LEGACY_STRATEGY_PARAMETERS = {
    "ma_cross": ("fast_period", "slow_period"),
    "momentum_breakout": ("lookback_period",),
    "rsi_reversion": ("rsi_period", "buy_threshold", "sell_threshold"),
}


class QuantStrategyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="ma_cross", min_length=1, max_length=64)
    version: str | None = Field(default=None, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    parameters: dict[str, ParameterValue] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_parameters(cls, value):
        if not isinstance(value, dict) or "parameters" in value:
            return value
        payload = dict(value)
        strategy_type = str(payload.get("type", "ma_cross"))
        payload["parameters"] = {
            name: payload[name]
            for name in _LEGACY_STRATEGY_PARAMETERS.get(strategy_type, ())
            if name in payload
        }
        return payload


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
        if self.end_date > date.today():
            raise ValueError("结束日期不能晚于今天")
        if (self.end_date - self.start_date).days > 5 * 366:
            raise ValueError("回测周期不能超过 5 年")
        return self


class QuantBacktestPayload(QuantBacktestCreate):
    strategy_snapshot: StrategySnapshot | None = None


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


class QuantMarketSnapshot(BaseModel):
    code: str
    source: str
    data_hash: str = ""
    items: list[KlineItem] = Field(default_factory=list)


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
    market_snapshots: list[QuantMarketSnapshot] = Field(default_factory=list)


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


class QuantStrategyParameterDescriptor(BaseModel):
    key: str
    type: Literal["integer", "number", "boolean", "string"]
    label: str
    description: str = ""
    default: ParameterValue
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: list[ParameterValue] = Field(default_factory=list)


class QuantStrategyConstraintDescriptor(BaseModel):
    operator: ComparisonOperator
    left: SignalOperand
    right: SignalOperand
    message: str


class QuantStrategyPreset(BaseModel):
    key: str
    version: str
    definition_hash: str
    name: str
    description: str
    scenario: str
    risk_level: Literal["low", "medium", "high"]
    presentation: dict[str, str]
    parameters: list[QuantStrategyParameterDescriptor]
    constraints: list[QuantStrategyConstraintDescriptor]
    config: QuantStrategyConfig


class QuantStrategyRegistryStatus(BaseModel):
    directory: str
    published_directory: str | None
    ledger_path: str | None
    generation: int
    loaded_at: float | None
    last_attempt_at: float | None
    last_error: str | None
    strategy_count: int
    latest_versions: dict[str, str]


QuantStrategyDraftStatus = Literal["draft", "validated", "testing", "backtested", "published"]


class QuantStrategyDraftValidationReport(BaseModel):
    valid: bool
    definition_hash: str
    warnings: list[str] = Field(default_factory=list)


class QuantStrategyDraftQualityGate(BaseModel):
    passed: bool | None = None
    run_status: str = "pending"
    definition_hash: str
    minimum_trade_count: int = 1
    maximum_drawdown_pct: float = Field(default=80, gt=0, le=80)
    trade_count: int | None = None
    max_drawdown: float | None = None
    errors: list[str] = Field(default_factory=list)


class QuantStrategyDraft(BaseModel):
    id: str
    created_by: int
    prompt: str
    definition: StrategyDefinition
    definition_hash: str
    status: QuantStrategyDraftStatus
    validation: QuantStrategyDraftValidationReport | None = None
    backtest_run_id: str | None = None
    quality_gate: QuantStrategyDraftQualityGate | None = None
    published_path: str | None = None
    last_error: str | None = None
    created_at: float
    updated_at: float
    published_at: float | None = None


class QuantStrategyDraftGenerateRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=4000)


class QuantStrategyDraftUpdateRequest(BaseModel):
    expected_definition_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    definition: StrategyDefinition


class QuantStrategyDraftBacktestRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    universe: QuantUniverse
    execution: QuantExecutionConfig = Field(default_factory=QuantExecutionConfig)
    start_date: date
    end_date: date
    benchmark: str = Field(default="000300", min_length=6, max_length=8)
    minimum_trade_count: int = Field(default=1, ge=1, le=10_000)
    maximum_drawdown_pct: float = Field(default=80, gt=0, le=80)

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_date >= self.end_date:
            raise ValueError("开始日期必须早于结束日期")
        if self.end_date > date.today():
            raise ValueError("结束日期不能晚于今天")
        if (self.end_date - self.start_date).days > 5 * 366:
            raise ValueError("回测周期不能超过 5 年")
        return self


class QuantStrategyDraftPublishRequest(BaseModel):
    expected_definition_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class QuantStrategySave(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    config: QuantStrategyConfig


class QuantSavedStrategy(BaseModel):
    id: int
    name: str
    config: QuantStrategyConfig
    created_at: float
    updated_at: float
