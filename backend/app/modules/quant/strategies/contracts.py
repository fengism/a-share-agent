"""YAML 量化策略 DSL 的严格协议。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParameterValue = int | float | bool | str
ParameterReference = int | str
NumericValue = int | float
SignalOperand = NumericValue | str
ComparisonOperator = Literal[
    "greater_than",
    "greater_or_equal",
    "less_than",
    "less_or_equal",
]


def _matches_parameter_type(value: ParameterValue, parameter_type: str) -> bool:
    if parameter_type == "integer":
        return type(value) is int
    if parameter_type == "number":
        return type(value) in (int, float)
    if parameter_type == "boolean":
        return type(value) is bool
    return type(value) is str


class StrategyParameterDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    type: Literal["integer", "number", "boolean", "string"]
    label: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=160)
    default: ParameterValue
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = Field(default=None, gt=0)
    choices: tuple[ParameterValue, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def validate_definition(self):
        if not _matches_parameter_type(self.default, self.type):
            raise ValueError(f"参数默认值与类型 {self.type} 不匹配")
        if self.type not in {"integer", "number"} and any(
            value is not None for value in (self.minimum, self.maximum, self.step)
        ):
            raise ValueError("仅数值参数支持 minimum、maximum 和 step")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("参数 minimum 不能大于 maximum")
        numeric_default = float(self.default) if self.type in {"integer", "number"} else None
        if self.minimum is not None and numeric_default is not None and numeric_default < self.minimum:
            raise ValueError("参数默认值小于 minimum")
        if self.maximum is not None and numeric_default is not None and numeric_default > self.maximum:
            raise ValueError("参数默认值大于 maximum")
        if self.choices:
            if any(not _matches_parameter_type(choice, self.type) for choice in self.choices):
                raise ValueError("参数 choices 与参数类型不匹配")
            if self.default not in self.choices:
                raise ValueError("参数默认值必须包含在 choices 中")
        return self


class StrategyIndicatorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # rsi 为 Cutler RSI（简单滚动平均）；obv 输出为累计成交量 / 10_000。
    operator: Literal[
        "sma",
        "ema",
        "rsi",
        "rolling_max",
        "rolling_min",
        "rolling_std",
        "add",
        "subtract",
        "multiply",
        "divide",
        "obv",
        "shift",
        "atr",
        "momentum",
        "min",
        "max",
        "abs",
    ]
    input: str | None = Field(default=None, min_length=1, max_length=64)
    volume_input: str | None = Field(default=None, min_length=1, max_length=64)
    period: ParameterReference | None = None
    left: SignalOperand | None = None
    right: SignalOperand | None = None
    zero_value: SignalOperand | None = None
    offset: ParameterReference = 0

    @model_validator(mode="after")
    def validate_shape(self):
        window_operators = {"sma", "ema", "rsi", "rolling_max", "rolling_min", "rolling_std", "shift", "momentum"}
        arithmetic_operators = {"add", "subtract", "multiply", "divide", "min", "max"}
        if any(type(value) is bool for value in (self.left, self.right, self.zero_value)):
            raise ValueError("指标操作数不能是布尔值")
        if self.operator in window_operators:
            if self.input is None or self.period is None:
                raise ValueError(f"{self.operator} 必须提供 input 和 period")
            if any(value is not None for value in (self.volume_input, self.left, self.right, self.zero_value)):
                raise ValueError(f"{self.operator} 不支持算术或成交量字段")
        elif self.operator in arithmetic_operators:
            if self.left is None or self.right is None:
                raise ValueError(f"{self.operator} 必须提供 left 和 right")
            if self.input is not None or self.volume_input is not None or self.period is not None:
                raise ValueError(f"{self.operator} 只能提供算术操作数")
            if self.zero_value is not None and self.operator != "divide":
                raise ValueError("仅 divide 支持 zero_value")
        elif self.operator == "atr":
            if self.period is None:
                raise ValueError("atr 必须提供 period")
            if any(value is not None for value in (self.volume_input, self.left, self.right, self.zero_value)):
                raise ValueError("atr 不支持算术或成交量字段")
        elif self.operator == "abs":
            if self.left is None and self.input is None:
                raise ValueError("abs 必须提供 left 或 input")
            if any(value is not None for value in (self.period, self.volume_input, self.right, self.zero_value)):
                raise ValueError("abs 只能提供单一操作数")
        elif self.operator == "obv":
            if self.input is None or self.volume_input is None:
                raise ValueError("obv 必须提供 input 和 volume_input")
            if any(value is not None for value in (self.period, self.left, self.right, self.zero_value)):
                raise ValueError("obv 不支持 period 或算术操作数")
        return self


class StrategySignalExpression(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: Literal[
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "cross_above",
        "cross_below",
        "and",
        "or",
        "not",
    ]
    left: SignalOperand | None = None
    right: SignalOperand | None = None
    operands: tuple[StrategySignalExpression, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def validate_shape(self):
        if type(self.left) is bool or type(self.right) is bool:
            raise ValueError("信号操作数不能是布尔值")
        if self.operator in {
            "greater_than",
            "greater_or_equal",
            "less_than",
            "less_or_equal",
            "cross_above",
            "cross_below",
        }:
            if self.left is None or self.right is None or self.operands:
                raise ValueError(f"{self.operator} 必须只提供 left 和 right")
        elif self.operator == "not":
            if len(self.operands) != 1 or self.left is not None or self.right is not None:
                raise ValueError("not 必须只提供一个 operands 项")
        elif len(self.operands) < 2 or self.left is not None or self.right is not None:
            raise ValueError(f"{self.operator} 必须提供至少两个 operands 项")
        return self


class StrategySignals(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry: StrategySignalExpression
    exit: StrategySignalExpression


class StrategyParameterConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: ComparisonOperator
    left: SignalOperand
    right: SignalOperand
    message: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_operands(self):
        if type(self.left) is bool or type(self.right) is bool:
            raise ValueError("参数约束操作数不能是布尔值")
        return self


class StrategyPositionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["binary", "continuous_weight"] = "binary"
    target_weight: SignalOperand | None = None


class StrategyPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    icon: str = Field(default="line-chart", min_length=1, max_length=40)


class StrategyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_version: Literal["quant.strategy/v1", "quant.strategy/v2"]
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    enabled: bool = True
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)
    scenario: str = Field(min_length=1, max_length=80)
    risk_level: Literal["low", "medium", "high"]
    presentation: StrategyPresentation = Field(default_factory=StrategyPresentation)
    parameters: dict[str, StrategyParameterDefinition] = Field(default_factory=dict)
    constraints: tuple[StrategyParameterConstraint, ...] = Field(default=(), max_length=20)
    indicators: dict[str, StrategyIndicatorDefinition] = Field(min_length=1, max_length=64)
    signals: StrategySignals
    position: StrategyPositionDefinition = Field(default_factory=StrategyPositionDefinition)

    @model_validator(mode="after")
    def validate_names(self):
        identifier_pattern = r"^[a-z][a-z0-9_]{0,63}$"
        from re import fullmatch

        invalid_parameters = [name for name in self.parameters if fullmatch(identifier_pattern, name) is None]
        invalid_indicators = [name for name in self.indicators if fullmatch(identifier_pattern, name) is None]
        if invalid_parameters:
            raise ValueError(f"参数名称不合法: {invalid_parameters[0]}")
        if invalid_indicators:
            raise ValueError(f"指标名称不合法: {invalid_indicators[0]}")
        return self


class StrategySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    version: str
    definition_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parameters: dict[str, ParameterValue]
    definition: StrategyDefinition


StrategySignalExpression.model_rebuild()
