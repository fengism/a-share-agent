"""校验策略引用并编译确定性指标执行顺序。"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.quant.strategies.contracts import (
    SignalOperand,
    StrategyDefinition,
    StrategySignalExpression,
)
from app.modules.quant.strategies.loader import canonical_definition_hash

DATA_FIELDS = frozenset({"open", "high", "low", "close", "volume"})

# 持仓路径依赖的运行时序列：由 evaluator 在扫描持仓状态时填充，
# 仅在持仓中有值（空仓时为 None，信号比较按 False 处理），用于表达跟踪止损类退出条件
ARITHMETIC_OPERATORS = frozenset({"add", "subtract", "multiply", "divide"})

RUNTIME_SERIES = frozenset({
    "entry_price",          # 本轮持仓的入场价
    "holding_bars",         # 本轮持仓已持有的 bar 数（入场当日为 1）
    "highest_since_entry",  # 本轮持仓期间的最高 high
    "lowest_since_entry",   # 本轮持仓期间的最低 low
})
MAX_EXPRESSION_DEPTH = 12


@dataclass(frozen=True, slots=True)
class CompiledStrategy:
    definition: StrategyDefinition
    definition_hash: str
    indicator_order: tuple[str, ...]
    # 传递依赖运行时序列的算术指标：在持仓扫描时逐 bar 求值
    runtime_indicators: tuple[str, ...] = ()


def _parameter_name(value: int | str) -> str | None:
    return value[1:] if isinstance(value, str) and value.startswith("$") else None


def _validate_numeric_argument(
    definition: StrategyDefinition,
    value: int | str,
    label: str,
    *,
    minimum: int,
) -> None:
    parameter_name = _parameter_name(value)
    if parameter_name is None:
        if type(value) is not int or value < minimum:
            raise ValueError(f"{label} 必须是不小于 {minimum} 的整数或参数引用")
        return
    parameter = definition.parameters.get(parameter_name)
    if parameter is None:
        raise ValueError(f"{label} 引用了未知参数: {parameter_name}")
    if parameter.type != "integer":
        raise ValueError(f"{label} 只能引用整数参数: {parameter_name}")


def _validate_operand(definition: StrategyDefinition, value: SignalOperand, label: str) -> None:
    if not isinstance(value, str):
        return
    if value.startswith("$"):
        parameter = definition.parameters.get(value[1:])
        if parameter is None:
            raise ValueError(f"{label} 引用了未知参数: {value[1:]}")
        if parameter.type not in {"integer", "number"}:
            raise ValueError(f"{label} 只能引用数值参数: {value[1:]}")
        return
    if value not in DATA_FIELDS and value not in RUNTIME_SERIES and value not in definition.indicators:
        raise ValueError(f"{label} 引用了未知数据或指标: {value}")


def _validate_expression(
    definition: StrategyDefinition,
    expression: StrategySignalExpression,
    *,
    depth: int = 1,
) -> None:
    if depth > MAX_EXPRESSION_DEPTH:
        raise ValueError(f"信号表达式深度超过限制: {MAX_EXPRESSION_DEPTH}")
    if expression.left is not None:
        _validate_operand(definition, expression.left, "left")
    if expression.right is not None:
        _validate_operand(definition, expression.right, "right")
    for operand in expression.operands:
        _validate_expression(definition, operand, depth=depth + 1)


def _indicator_order(definition: StrategyDefinition) -> tuple[str, ...]:
    visiting: set[str] = set()
    visited: set[str] = set()
    order: list[str] = []

    def dependencies(name: str) -> tuple[str, ...]:
        indicator = definition.indicators[name]
        values = (
            indicator.input,
            indicator.volume_input,
            indicator.left,
            indicator.right,
            indicator.zero_value,
        )
        return tuple(
            value
            for value in values
            if isinstance(value, str) and not value.startswith("$")
        )

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"指标存在循环依赖: {name}")
        visiting.add(name)
        for dependency in dependencies(name):
            if dependency in definition.indicators:
                visit(dependency)
            elif dependency not in DATA_FIELDS and dependency not in RUNTIME_SERIES:
                raise ValueError(f"指标 {name} 引用了未知输入: {dependency}")
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for indicator_name, indicator in definition.indicators.items():
        if indicator.period is not None:
            _validate_numeric_argument(
                definition,
                indicator.period,
                f"指标 {indicator_name} period",
                minimum=1,
            )
        _validate_numeric_argument(
            definition,
            indicator.offset,
            f"指标 {indicator_name} offset",
            minimum=0,
        )
        for label, value in (
            ("input", indicator.input),
            ("volume_input", indicator.volume_input),
            ("left", indicator.left),
            ("right", indicator.right),
            ("zero_value", indicator.zero_value),
        ):
            if value is not None:
                _validate_operand(definition, value, f"指标 {indicator_name} {label}")
        visit(indicator_name)
    return tuple(order)


def compile_strategy(
    definition: StrategyDefinition,
    definition_hash: str | None = None,
) -> CompiledStrategy:
    order = _indicator_order(definition)
    _validate_expression(definition, definition.signals.entry)
    _validate_expression(definition, definition.signals.exit)
    for constraint in definition.constraints:
        _validate_operand(definition, constraint.left, "约束 left")
        _validate_operand(definition, constraint.right, "约束 right")
        if any(isinstance(operand, str) and not operand.startswith("$") for operand in (constraint.left, constraint.right)):
            raise ValueError("参数约束只能引用参数或数值字面量")
    runtime_indicators = _runtime_dependent_indicators(definition, order)
    return CompiledStrategy(
        definition=definition,
        definition_hash=definition_hash or canonical_definition_hash(definition),
        indicator_order=order,
        runtime_indicators=runtime_indicators,
    )


def _runtime_dependent_indicators(definition: StrategyDefinition, order: tuple[str, ...]) -> tuple[str, ...]:
    """找出（传递）依赖运行时序列的指标，仅允许算术算子（逐 bar 求值）。"""
    dependent: set[str] = set()
    for name in order:
        indicator = definition.indicators[name]
        values = (indicator.input, indicator.volume_input, indicator.left, indicator.right, indicator.zero_value)
        deps = {v for v in values if isinstance(v, str) and not v.startswith("$")}
        if any(dep in RUNTIME_SERIES or dep in dependent for dep in deps):
            if indicator.operator not in ARITHMETIC_OPERATORS:
                raise ValueError(f"指标 {name} 依赖运行时序列，只支持算术算子")
            dependent.add(name)
    return tuple(name for name in order if name in dependent)
