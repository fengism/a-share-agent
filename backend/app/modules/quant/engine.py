"""不依赖网络和存储的确定性组合回测引擎。"""

import hashlib
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from app.domain.market import KlineItem
from app.modules.quant.schemas import (
    QuantBacktestResult,
    QuantEquityPoint,
    QuantExecutionConfig,
    QuantMetrics,
    QuantMonthlyReturn,
    QuantStrategyConfig,
    QuantTrade,
)
from app.modules.quant.strategies.compiler import compile_strategy
from app.modules.quant.strategies.contracts import StrategySnapshot
from app.modules.quant.strategies.evaluator import evaluate_target_positions
from app.modules.quant.strategies.registry import get_strategy_registry

ENGINE_VERSION = "2026-08-18-v3"


@dataclass(slots=True)
class _PortfolioState:
    cash: float
    holdings: dict[str, int]
    average_cost: dict[str, float]
    peak_equity: float
    last_prices: dict[str, float] = field(default_factory=dict)
    trades: list[QuantTrade] = field(default_factory=list)


def build_target_positions(
    items: list[KlineItem],
    strategy: QuantStrategyConfig | StrategySnapshot,
) -> list[int]:
    snapshot = (
        strategy
        if isinstance(strategy, StrategySnapshot)
        else get_strategy_registry().resolve(strategy.type, strategy.version, strategy.parameters)
    )
    compiled = compile_strategy(snapshot.definition, snapshot.definition_hash)
    return evaluate_target_positions(items, compiled, snapshot.parameters)


def strategy_warmup_bars(strategy: QuantStrategyConfig | StrategySnapshot) -> int:
    snapshot = (
        strategy
        if isinstance(strategy, StrategySnapshot)
        else get_strategy_registry().resolve(strategy.type, strategy.version, strategy.parameters)
    )
    compiled = compile_strategy(snapshot.definition, snapshot.definition_hash)
    warmup: dict[str, int] = {name: 0 for name in ("open", "high", "low", "close", "volume")}

    def argument(value: int | str | None, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, str) and value.startswith("$"):
            return int(snapshot.parameters[value[1:]])
        return int(value)

    def operand(value) -> int:
        if not isinstance(value, str) or value.startswith("$"):
            return 0
        return warmup.get(value, 0)

    for name in compiled.indicator_order:
        indicator = compiled.definition.indicators[name]
        offset = argument(indicator.offset)
        if indicator.operator in {"add", "subtract", "multiply", "divide"}:
            required = max(operand(indicator.left), operand(indicator.right))
        elif indicator.operator == "obv":
            required = max(warmup.get(indicator.input or "", 0), warmup.get(indicator.volume_input or "", 0))
        else:
            period = argument(indicator.period, 1)
            input_warmup = warmup.get(indicator.input or "", 0)
            if indicator.operator in {"rsi", "shift"}:
                required = input_warmup + period
            else:
                required = input_warmup + max(0, period - 1)
        warmup[name] = required + offset
    return max(warmup.values(), default=0)


def _commission(amount: float, execution: QuantExecutionConfig) -> float:
    return float(max(amount * execution.commission_rate, execution.minimum_commission))


def _trade_fee(amount: float, side: str, execution: QuantExecutionConfig) -> float:
    fee = _commission(amount, execution) + amount * execution.transfer_fee_rate
    if side == "sell":
        fee += amount * execution.stamp_duty_rate
    return float(fee)


def _is_tradeable(item: KlineItem, side: str) -> bool:
    if item.volume <= 0 or min(item.open, item.high, item.low) <= 0:
        return False
    one_price = math.isclose(item.open, item.high) and math.isclose(item.open, item.low)
    if one_price and item.pre_close not in (None, 0):
        if side == "buy" and item.open > item.pre_close:
            return False
        if side == "sell" and item.open < item.pre_close:
            return False
    return True


def _daily_returns(values: list[float]) -> list[float]:
    return [values[index] / values[index - 1] - 1 for index in range(1, len(values)) if values[index - 1] > 0]


def _annualized_return(total_return: float, observations: int) -> float:
    if observations <= 1 or total_return <= -1:
        return total_return
    return float((1 + total_return) ** (252 / (observations - 1)) - 1)


def _percent(value: float) -> float:
    return round(value * 100, 6)


def _monthly_returns(points: list[QuantEquityPoint]) -> list[QuantMonthlyReturn]:
    month_values: dict[str, list[float]] = defaultdict(list)
    for point in points:
        month_values[point.date[:7]].append(point.equity)
    result = []
    previous_close = points[0].equity if points else 0
    for month in sorted(month_values):
        values = month_values[month]
        month_return = values[-1] / previous_close - 1 if previous_close else 0
        result.append(QuantMonthlyReturn(month=month, return_pct=_percent(month_return)))
        previous_close = values[-1]
    return result


def _build_metrics(
    points: list[QuantEquityPoint],
    trades: list[QuantTrade],
    initial_cash: float,
    risk_free_rate: float,
) -> QuantMetrics:
    equities = [point.equity for point in points]
    total_return = equities[-1] / initial_cash - 1 if equities else 0
    returns = _daily_returns(equities)
    volatility = statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else 0
    excess_daily = (statistics.fmean(returns) - risk_free_rate / 252) if returns else 0
    sharpe = excess_daily / statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 and statistics.pstdev(returns) > 0 else None
    realized = [trade.realized_pnl for trade in trades if trade.side == "sell" and trade.realized_pnl is not None]
    wins = [value for value in realized if value > 0]
    losses = [value for value in realized if value < 0]
    win_rate = len(wins) / len(realized) if realized else None
    profit_loss_ratio = (
        statistics.fmean(wins) / abs(statistics.fmean(losses)) if wins and losses else None
    )
    average_equity = statistics.fmean(equities) if equities else initial_cash
    turnover = sum(trade.amount for trade in trades) / average_equity if average_equity else 0
    benchmark_values = [point.benchmark for point in points if point.benchmark is not None]
    benchmark_return = benchmark_values[-1] / benchmark_values[0] - 1 if len(benchmark_values) > 1 else None
    return QuantMetrics(
        total_return=_percent(total_return),
        annualized_return=_percent(_annualized_return(total_return, len(equities))),
        benchmark_return=_percent(benchmark_return) if benchmark_return is not None else None,
        excess_return=_percent(total_return - benchmark_return) if benchmark_return is not None else None,
        annualized_volatility=_percent(volatility),
        sharpe_ratio=round(sharpe, 6) if sharpe is not None else None,
        max_drawdown=_percent(min((point.drawdown for point in points), default=0)),
        win_rate=_percent(win_rate) if win_rate is not None else None,
        profit_loss_ratio=round(profit_loss_ratio, 6) if profit_loss_ratio is not None else None,
        turnover_rate=_percent(turnover),
        trade_count=len(trades),
    )


def _update_execution_targets(
    current_date: str,
    bars_by_code: dict[str, list[KlineItem]],
    date_indexes: dict[str, dict[str, int]],
    targets: dict[str, list[int]],
    previous_targets: dict[str, int],
    execution_targets: dict[str, int],
) -> bool:
    changed = False
    for code in bars_by_code:
        index = date_indexes[code].get(current_date)
        if index is None or index == 0:
            continue
        execution_targets[code] = targets[code][index - 1]
        changed = changed or execution_targets[code] != previous_targets[code]
        previous_targets[code] = execution_targets[code]
    return changed


def _build_desired_shares(
    codes: dict[str, list[KlineItem]],
    execution_targets: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> tuple[list[str], dict[str, int]]:
    active_codes = [code for code, target in execution_targets.items() if target == 1]
    open_equity = state.cash + sum(
        state.holdings[code] * state.last_prices.get(code, state.average_cost[code])
        for code in state.holdings
    )
    target_value = open_equity / len(active_codes) if active_codes else 0
    desired_shares = {}
    for code in codes:
        reference_price = state.last_prices.get(code)
        desired_shares[code] = (
            int(target_value / reference_price / execution.lot_size) * execution.lot_size
            if execution_targets[code] == 1 and reference_price
            else 0
        )
    return active_codes, desired_shares


def _sell_excess_positions(
    current_date: str,
    codes: dict[str, list[KlineItem]],
    available_bars: dict[str, KlineItem],
    desired_shares: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> None:
    for code in codes:
        shares = state.holdings[code] - desired_shares[code]
        if shares <= 0 or code not in available_bars or not _is_tradeable(available_bars[code], "sell"):
            continue
        price = available_bars[code].open * (1 - execution.slippage_bps / 10_000)
        amount = price * shares
        fee = _trade_fee(amount, "sell", execution)
        realized_pnl = (price - state.average_cost[code]) * shares - fee
        state.cash += amount - fee
        state.holdings[code] -= shares
        if state.holdings[code] == 0:
            state.average_cost[code] = 0
        state.trades.append(
            QuantTrade(
                date=current_date,
                code=code,
                side="sell",
                price=price,
                shares=shares,
                amount=amount,
                fee=fee,
                realized_pnl=realized_pnl,
            )
        )


def _buy_shortfall_positions(
    current_date: str,
    active_codes: list[str],
    available_bars: dict[str, KlineItem],
    desired_shares: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> None:
    for code in active_codes:
        shares = desired_shares[code] - state.holdings[code]
        if shares <= 0 or code not in available_bars or not _is_tradeable(available_bars[code], "buy"):
            continue
        price = available_bars[code].open * (1 + execution.slippage_bps / 10_000)
        while shares > 0:
            amount = price * shares
            fee = _trade_fee(amount, "buy", execution)
            if amount + fee <= state.cash:
                break
            shares -= execution.lot_size
        if shares <= 0:
            continue
        amount = price * shares
        fee = _trade_fee(amount, "buy", execution)
        previous_value = state.average_cost[code] * state.holdings[code]
        state.cash -= amount + fee
        state.holdings[code] += shares
        state.average_cost[code] = (previous_value + amount + fee) / state.holdings[code]
        state.trades.append(
            QuantTrade(
                date=current_date,
                code=code,
                side="buy",
                price=price,
                shares=shares,
                amount=amount,
                fee=fee,
            )
        )


def _rebalance_portfolio(
    current_date: str,
    bars_by_code: dict[str, list[KlineItem]],
    available_bars: dict[str, KlineItem],
    execution_targets: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> bool:
    active_codes, desired_shares = _build_desired_shares(
        bars_by_code,
        execution_targets,
        state,
        execution,
    )
    _sell_excess_positions(
        current_date,
        bars_by_code,
        available_bars,
        desired_shares,
        state,
        execution,
    )
    _buy_shortfall_positions(
        current_date,
        active_codes,
        available_bars,
        desired_shares,
        state,
        execution,
    )
    return any(
        (execution_targets[code] == 0 and state.holdings[code] > 0)
        or (execution_targets[code] == 1 and code not in available_bars and state.holdings[code] == 0)
        or abs(state.holdings[code] - desired_shares[code]) >= execution.lot_size
        for code in bars_by_code
    )


def _build_equity_point(
    current_date: str,
    available_bars: dict[str, KlineItem],
    benchmark_map: dict[str, float],
    benchmark_start: float | None,
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> QuantEquityPoint:
    for code, item in available_bars.items():
        state.last_prices[code] = item.close
    equity = state.cash + sum(
        state.holdings[code] * state.last_prices.get(code, state.average_cost[code])
        for code in state.holdings
    )
    state.peak_equity = max(state.peak_equity, equity)
    benchmark_value = None
    if benchmark_start and current_date in benchmark_map:
        benchmark_value = execution.initial_cash * benchmark_map[current_date] / benchmark_start
    return QuantEquityPoint(
        date=current_date,
        equity=round(equity, 2),
        benchmark=round(benchmark_value, 2) if benchmark_value is not None else None,
        drawdown=equity / state.peak_equity - 1 if state.peak_equity else 0,
    )


def run_backtest(
    bars_by_code: dict[str, list[KlineItem]],
    benchmark_items: list[KlineItem],
    strategy: QuantStrategyConfig | StrategySnapshot,
    execution: QuantExecutionConfig,
    *,
    data_hashes: list[str],
    data_sources: list[str],
    evaluation_start_date: str | None = None,
    evaluation_end_date: str | None = None,
) -> QuantBacktestResult:
    if not bars_by_code:
        raise ValueError("股票池没有可用行情")
    bar_maps = {code: {item.date: item for item in items} for code, items in bars_by_code.items()}
    date_indexes = {
        code: {item.date: index for index, item in enumerate(items)}
        for code, items in bars_by_code.items()
    }
    targets = {code: build_target_positions(items, strategy) for code, items in bars_by_code.items()}
    previous_targets = {code: 0 for code in bars_by_code}
    execution_targets = {code: 0 for code in bars_by_code}
    state = _PortfolioState(
        cash=execution.initial_cash,
        holdings={code: 0 for code in bars_by_code},
        average_cost={code: 0.0 for code in bars_by_code},
        peak_equity=execution.initial_cash,
    )
    points: list[QuantEquityPoint] = []
    all_dates = sorted(
        day
        for day in {item.date for items in bars_by_code.values() for item in items}
        if (evaluation_start_date is None or day >= evaluation_start_date)
        and (evaluation_end_date is None or day <= evaluation_end_date)
    )
    benchmark_map = {item.date: item.close for item in benchmark_items}
    benchmark_start = next((benchmark_map[day] for day in all_dates if day in benchmark_map), None)
    rebalance_days_remaining = 0

    for current_date in all_dates:
        available_bars = {code: bar_maps[code][current_date] for code in bars_by_code if current_date in bar_maps[code]}
        if _update_execution_targets(
            current_date,
            bars_by_code,
            date_indexes,
            targets,
            previous_targets,
            execution_targets,
        ):
            rebalance_days_remaining = 3

        for code, item in available_bars.items():
            state.last_prices[code] = item.open

        if rebalance_days_remaining > 0:
            unresolved = _rebalance_portfolio(
                current_date,
                bars_by_code,
                available_bars,
                execution_targets,
                state,
                execution,
            )
            rebalance_days_remaining = rebalance_days_remaining - 1 if unresolved else 0

        points.append(
            _build_equity_point(
                current_date,
                available_bars,
                benchmark_map,
                benchmark_start,
                state,
                execution,
            )
        )

    if not points:
        raise ValueError("回测区间没有共同交易数据")
    combined_hash = hashlib.sha256(
        json.dumps(sorted(data_hashes), separators=(",", ":")).encode()
    ).hexdigest()
    return QuantBacktestResult(
        engine_version=ENGINE_VERSION,
        data_hash=combined_hash,
        data_sources=sorted(set(data_sources)),
        codes=sorted(bars_by_code),
        metrics=_build_metrics(points, state.trades, execution.initial_cash, execution.risk_free_rate),
        equity_curve=points,
        monthly_returns=_monthly_returns(points),
        trades=state.trades,
    )
