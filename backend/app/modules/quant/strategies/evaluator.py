"""执行编译后的指标与二元仓位信号。"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import cast

from app.domain.market import KlineItem
from app.modules.quant.strategies.compiler import CompiledStrategy
from app.modules.quant.strategies.contracts import (
    NumericValue,
    ParameterValue,
    SignalOperand,
    StrategyIndicatorDefinition,
    StrategySignalExpression,
)


def _integer_argument(value: int | str, parameters: dict[str, ParameterValue]) -> int:
    resolved = parameters[value[1:]] if isinstance(value, str) and value.startswith("$") else value
    return int(resolved)


def _complete_window(values: Sequence[float | None], period: int) -> list[float] | None:
    if len(values) != period or any(value is None for value in values):
        return None
    return [value for value in values if value is not None]


def _sma(values: Sequence[float | None], period: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window = values[index - period + 1 : index + 1]
        complete = _complete_window(window, period)
        result.append(sum(complete) / period if complete is not None else None)
    return result


def _ema(values: Sequence[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    multiplier = 2 / (period + 1)
    previous: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period or value is None:
            continue
        if previous is None:
            window = values[index - period + 1 : index + 1]
            complete = _complete_window(window, period)
            if complete is None:
                continue
            previous = sum(complete) / period
        else:
            previous = (float(value) - previous) * multiplier + previous
        result[index] = previous
    return result


def _rsi(values: Sequence[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(period, len(values)):
        window = values[index - period : index + 1]
        complete = _complete_window(window, period + 1)
        if complete is None:
            continue
        changes = [complete[position] - complete[position - 1] for position in range(1, len(complete))]
        gains = sum(max(change, 0) for change in changes) / period
        losses = sum(max(-change, 0) for change in changes) / period
        result[index] = 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)
    return result


def _rolling(values: Sequence[float | None], period: int, mode: str) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window = values[index - period + 1 : index + 1]
        complete = _complete_window(window, period)
        if complete is None:
            result.append(None)
        elif mode == "rolling_max":
            result.append(float(max(complete)))
        elif mode == "rolling_min":
            result.append(float(min(complete)))
        else:
            result.append(float(statistics.pstdev(complete)))
    return result


def _obv(
    closes: Sequence[float | None],
    volumes: Sequence[float | None],
) -> list[float | None]:
    result: list[float | None] = [0.0] * len(closes)
    current = 0.0
    for index in range(1, len(closes)):
        close = closes[index]
        previous_close = closes[index - 1]
        volume = volumes[index]
        if close is None or previous_close is None or volume is None:
            result[index] = None
            continue
        if close > previous_close:
            current += volume
        elif close < previous_close:
            current -= volume
        result[index] = current / 10_000
    return result


def _shift(values: Sequence[float | None], offset: int) -> list[float | None]:
    if offset == 0:
        return list(values)
    return [None] * offset + list(values[:-offset])


def _resolve_operand(
    value: SignalOperand,
    index: int,
    series: dict[str, list[float | None]],
    parameters: dict[str, ParameterValue],
) -> NumericValue | None:
    if not isinstance(value, str):
        return value
    if value.startswith("$"):
        resolved = parameters[value[1:]]
        if type(resolved) not in (int, float):
            raise ValueError(f"信号参数必须是数值: {value[1:]}")
        return cast(NumericValue, resolved)
    return series[value][index]


def _arithmetic_series(
    indicator: StrategyIndicatorDefinition,
    series: dict[str, list[float | None]],
    parameters: dict[str, ParameterValue],
    length: int,
) -> list[float | None]:
    if indicator.left is None or indicator.right is None:
        raise ValueError(f"算术指标缺少操作数: {indicator.operator}")
    result: list[float | None] = []
    for index in range(length):
        left = _resolve_operand(indicator.left, index, series, parameters)
        right = _resolve_operand(indicator.right, index, series, parameters)
        if left is None or right is None:
            result.append(None)
            continue
        if indicator.operator == "add":
            result.append(float(left + right))
        elif indicator.operator == "subtract":
            result.append(float(left - right))
        elif indicator.operator == "multiply":
            result.append(float(left * right))
        elif right != 0:
            result.append(float(left / right))
        elif indicator.zero_value is not None:
            zero_value = _resolve_operand(indicator.zero_value, index, series, parameters)
            result.append(float(zero_value) if zero_value is not None else None)
        else:
            result.append(None)
    return result


def _compare(operator: str, left: NumericValue, right: NumericValue) -> bool:
    if operator == "greater_than":
        return left > right
    if operator == "greater_or_equal":
        return left >= right
    if operator == "less_than":
        return left < right
    return left <= right


def _evaluate_expression(
    expression: StrategySignalExpression,
    index: int,
    series: dict[str, list[float | None]],
    parameters: dict[str, ParameterValue],
) -> bool:
    if expression.operator == "and":
        return all(_evaluate_expression(item, index, series, parameters) for item in expression.operands)
    if expression.operator == "or":
        return any(_evaluate_expression(item, index, series, parameters) for item in expression.operands)
    if expression.operator == "not":
        return not _evaluate_expression(expression.operands[0], index, series, parameters)

    if expression.left is None or expression.right is None:
        return False
    left_operand = expression.left
    right_operand = expression.right
    left = _resolve_operand(left_operand, index, series, parameters)
    right = _resolve_operand(right_operand, index, series, parameters)
    if left is None or right is None:
        return False
    if expression.operator in {"cross_above", "cross_below"}:
        if index == 0:
            return False
        previous_left = _resolve_operand(left_operand, index - 1, series, parameters)
        previous_right = _resolve_operand(right_operand, index - 1, series, parameters)
        if previous_left is None or previous_right is None:
            return False
        if expression.operator == "cross_above":
            return previous_left <= previous_right and left > right
        return previous_left >= previous_right and left < right
    return _compare(expression.operator, left, right)


def evaluate_target_positions(
    items: list[KlineItem],
    strategy: CompiledStrategy,
    parameters: dict[str, ParameterValue],
) -> list[int]:
    series: dict[str, list[float | None]] = {
        "open": [item.open for item in items],
        "high": [item.high for item in items],
        "low": [item.low for item in items],
        "close": [item.close for item in items],
        "volume": [item.volume for item in items],
    }
    for name in strategy.indicator_order:
        indicator = strategy.definition.indicators[name]
        offset = _integer_argument(indicator.offset, parameters)
        if indicator.operator in {"add", "subtract", "multiply", "divide"}:
            values = _arithmetic_series(indicator, series, parameters, len(items))
        elif indicator.operator == "obv":
            if indicator.input is None or indicator.volume_input is None:
                raise ValueError("obv 指标缺少输入")
            values = _obv(series[indicator.input], series[indicator.volume_input])
        else:
            if indicator.input is None or indicator.period is None:
                raise ValueError(f"指标 {name} 缺少 input 或 period")
            period = _integer_argument(indicator.period, parameters)
            source = series[indicator.input]
            if indicator.operator == "sma":
                values = _sma(source, period)
            elif indicator.operator == "ema":
                values = _ema(source, period)
            elif indicator.operator == "rsi":
                values = _rsi(source, period)
            elif indicator.operator == "shift":
                values = _shift(source, period)
            else:
                values = _rolling(source, period, indicator.operator)
        series[name] = _shift(values, offset)

    targets: list[int] = []
    current = 0
    for index in range(len(items)):
        if _evaluate_expression(strategy.definition.signals.entry, index, series, parameters):
            current = 1
        elif _evaluate_expression(strategy.definition.signals.exit, index, series, parameters):
            current = 0
        targets.append(current)
    return targets
