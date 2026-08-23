"""执行编译后的指标与二元仓位信号。"""

from __future__ import annotations

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
    # 滚动累加和实现，窗口内含 None 时结果为 None（与逐窗口切片语义一致）
    result: list[float | None] = []
    window_sum = 0.0
    window_none = 0
    for index, value in enumerate(values):
        if value is None:
            window_none += 1
        else:
            window_sum += float(value)
        if index >= period:
            leaving = values[index - period]
            if leaving is None:
                window_none -= 1
            else:
                window_sum -= float(leaving)
        if index >= period - 1 and window_none == 0:
            result.append(window_sum / period)
        else:
            result.append(None)
    return result


def _ema(values: Sequence[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    multiplier = 2 / (period + 1)
    previous: float | None = None
    since_seed = 0
    for index, value in enumerate(values):
        if value is None:
            # 停牌缺口后用停牌前的 EMA 续算会失真，复牌后重置种子重新起步
            previous = None
            since_seed = 0
            continue
        since_seed += 1
        if previous is None:
            if since_seed < period:
                continue
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
    # 滚动涨跌幅和实现；窗口内含 None 时结果为 None（与逐窗口切片语义一致）
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    gains = 0.0
    losses = 0.0
    window_none = 0
    for index in range(1, len(values)):
        change_index = index
        value = values[change_index]
        previous = values[change_index - 1]
        if value is None or previous is None:
            window_none += 1
        else:
            change = float(value) - float(previous)
            if change > 0:
                gains += change
            else:
                losses += -change
        leaving_index = index - period
        if leaving_index >= 1:
            leaving = values[leaving_index]
            leaving_previous = values[leaving_index - 1]
            if leaving is None or leaving_previous is None:
                window_none -= 1
            else:
                leaving_change = float(leaving) - float(leaving_previous)
                if leaving_change > 0:
                    gains -= leaving_change
                else:
                    losses -= -leaving_change
        if index >= period and window_none == 0:
            avg_gain = gains / period
            avg_loss = losses / period
            result[index] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return result


def _rolling(values: Sequence[float | None], period: int, mode: str) -> list[float | None]:
    result: list[float | None] = []
    if mode in {"rolling_max", "rolling_min"}:
        # 单调双端队列，窗口内含 None 时结果为 None
        from collections import deque

        extrema: deque[int] = deque()
        window_none = 0
        for index, value in enumerate(values):
            if value is None:
                window_none += 1
            else:
                if mode == "rolling_max":
                    while extrema and float(values[extrema[-1]]) <= float(value):
                        extrema.pop()
                else:
                    while extrema and float(values[extrema[-1]]) >= float(value):
                        extrema.pop()
                extrema.append(index)
            leaving_index = index - period
            if leaving_index >= 0:
                leaving = values[leaving_index]
                if leaving is None:
                    window_none -= 1
                elif extrema and extrema[0] == leaving_index:
                    extrema.popleft()
            if index >= period - 1 and window_none == 0 and extrema:
                result.append(float(values[extrema[0]]))
            else:
                result.append(None)
        return result

    # rolling_std：滚动平方和推导总体标准差
    window_sum = 0.0
    window_sq_sum = 0.0
    window_none = 0
    for index, value in enumerate(values):
        if value is None:
            window_none += 1
        else:
            number = float(value)
            window_sum += number
            window_sq_sum += number * number
        if index >= period:
            leaving = values[index - period]
            if leaving is None:
                window_none -= 1
            else:
                leaving_number = float(leaving)
                window_sum -= leaving_number
                window_sq_sum -= leaving_number * leaving_number
        if index >= period - 1 and window_none == 0:
            mean = window_sum / period
            variance = max(0.0, window_sq_sum / period - mean * mean)
            result.append(variance ** 0.5)
        else:
            result.append(None)
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
    runtime_indicator_names = set(strategy.runtime_indicators)
    for name in strategy.indicator_order:
        if name in runtime_indicator_names:
            # 依赖运行时序列的算术指标在持仓扫描时逐 bar 求值
            continue
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

    # 持仓路径依赖的运行时序列与依赖它们的算术指标：在持仓扫描时逐 bar 求值
    entry_price_series: list[float | None] = [None] * len(items)
    holding_bars_series: list[float | None] = [None] * len(items)
    highest_series: list[float | None] = [None] * len(items)
    lowest_series: list[float | None] = [None] * len(items)
    series["entry_price"] = entry_price_series
    series["holding_bars"] = holding_bars_series
    series["highest_since_entry"] = highest_series
    series["lowest_since_entry"] = lowest_series
    runtime_indicators = list(strategy.runtime_indicators)
    for name in runtime_indicators:
        if name not in series:
            series[name] = [None] * len(items)

    def evaluate_runtime_indicators(index: int) -> None:
        for name in runtime_indicators:
            indicator = strategy.definition.indicators[name]
            left = _resolve_operand(indicator.left, index, series, parameters) if indicator.left is not None else None
            right = _resolve_operand(indicator.right, index, series, parameters) if indicator.right is not None else None
            if left is None or right is None:
                series[name][index] = None
                continue
            if indicator.operator == "add":
                value = float(left + right)
            elif indicator.operator == "subtract":
                value = float(left - right)
            elif indicator.operator == "multiply":
                value = float(left * right)
            elif right != 0:
                value = float(left / right)
            elif indicator.zero_value is not None:
                zero_value = _resolve_operand(indicator.zero_value, index, series, parameters)
                value = float(zero_value) if zero_value is not None else None
            else:
                value = None
            series[name][index] = value

    targets: list[int] = []
    current = 0
    entry_price: float | None = None
    holding_bars = 0
    highest: float | None = None
    lowest: float | None = None

    def fill_runtime(index: int, item: KlineItem) -> None:
        entry_price_series[index] = entry_price
        holding_bars_series[index] = float(holding_bars)
        highest_series[index] = highest
        lowest_series[index] = lowest
        evaluate_runtime_indicators(index)

    for index, item in enumerate(items):
        if current == 1:
            # 持仓中的 bar：先累积路径状态并填充运行时序列，再评估退出条件
            holding_bars += 1
            highest = max(highest, item.high)
            lowest = min(lowest, item.low)
            fill_runtime(index, item)
            if _evaluate_expression(strategy.definition.signals.exit, index, series, parameters):
                current = 0
                entry_price = None
                holding_bars = 0
                highest = None
                lowest = None
            targets.append(current)
            continue

        if _evaluate_expression(strategy.definition.signals.entry, index, series, parameters):
            current = 1
            entry_price = item.close
            holding_bars = 1
            highest = item.high
            lowest = item.low
            fill_runtime(index, item)
        targets.append(current)
    return targets
