"""不依赖网络和存储的确定性组合回测引擎。"""

import hashlib
import json
import math
import statistics
import threading
from collections import OrderedDict, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.domain.market import KlineItem
from app.modules.quant.schemas import (
    QuantBacktestResult,
    QuantEquityPoint,
    QuantExecutionConfig,
    QuantHoldoutValidation,
    QuantMetrics,
    QuantMonthlyReturn,
    QuantOpenPosition,
    QuantStrategyConfig,
    QuantTrade,
)
from app.modules.quant.strategies.compiler import CompiledStrategy, compile_strategy
from app.modules.quant.strategies.contracts import StrategySnapshot
from app.modules.quant.strategies.evaluator import evaluate_target_positions
from app.modules.quant.strategies.registry import get_strategy_registry

ENGINE_VERSION = "2026-09-19-v10"
#: 年化收益/波动率换算用的每年交易日数（沪深 A 股惯例）。
TRADING_DAYS_PER_YEAR = 252
HOLDOUT_TRAINING_RATIO = 0.7
MIN_TRAINING_OBSERVATIONS = 40
MIN_HOLDOUT_OBSERVATIONS = 20

#: ``fee_schedule="a_share_historical"`` 支持的最早起始日。
A_SHARE_HISTORICAL_FEE_START = "2015-08-01"

#: 沪深 A 股过户费档期（双向计征）：（生效起始日, 费率），按生效日倒序排列。
_TRANSFER_FEE_SCHEDULE: tuple[tuple[str, float], ...] = (
    ("2022-04-29", 0.00001),  # 过户费总体下调 50%
    (A_SHARE_HISTORICAL_FEE_START, 0.00002),
)

#: 证券交易印花税档期（仅卖出方计征）：（生效起始日, 税率），按生效日倒序排列。
_STAMP_DUTY_SCHEDULE: tuple[tuple[str, float], ...] = (
    ("2023-08-28", 0.0005),  # 印花税减半征收
    (A_SHARE_HISTORICAL_FEE_START, 0.001),
)


class BacktestCancelled(RuntimeError):
    pass


def _check_cancelled(event: threading.Event | None) -> None:
    if event is not None and event.is_set():
        raise BacktestCancelled("回测计算已取消")


@dataclass(frozen=True, slots=True)
class _DeferredIntent:
    target: int | float
    side: Literal["buy", "sell"]


@dataclass(slots=True)
class _PortfolioState:
    cash: float
    holdings: dict[str, int]
    average_cost: dict[str, float]
    peak_equity: float
    last_prices: dict[str, float] = field(default_factory=dict)
    trades: list[QuantTrade] = field(default_factory=list)
    holding_highs: dict[str, float] = field(default_factory=dict)
    stopped_codes: set[str] = field(default_factory=set)
    drawdown_halted: bool = False
    risk_scale: float = 1.0
    turnover_date: str = ""
    daily_turnover: dict[str, float] = field(default_factory=dict)


def build_target_positions(
    items: list[KlineItem],
    strategy: QuantStrategyConfig | StrategySnapshot,
    *,
    evaluation_start_date: str | None = None,
) -> list[int | float]:
    snapshot = (
        strategy
        if isinstance(strategy, StrategySnapshot)
        else get_strategy_registry().resolve(strategy.type, strategy.version, strategy.parameters)
    )
    compiled = _compile_cached(snapshot)
    return evaluate_target_positions(
        items,
        compiled,
        snapshot.parameters,
        evaluation_start_date=evaluation_start_date,
    )


# 同一回测对每只股票重复调用 build_target_positions 时，编译与校验只需做一次。
# run_backtest 在线程池中执行，多回测可能并发访问，用锁保护并按 LRU 逐条驱逐。
_compiled_cache: OrderedDict[str, CompiledStrategy] = OrderedDict()
_COMPILED_CACHE_LIMIT = 64
_compiled_cache_lock = threading.Lock()


def _compile_cached(snapshot: StrategySnapshot) -> CompiledStrategy:
    with _compiled_cache_lock:
        cached = _compiled_cache.get(snapshot.definition_hash)
        if cached is not None:
            _compiled_cache.move_to_end(snapshot.definition_hash)
            return cached
    compiled = compile_strategy(snapshot.definition, snapshot.definition_hash)
    with _compiled_cache_lock:
        cached = _compiled_cache.get(snapshot.definition_hash)
        if cached is not None:
            _compiled_cache.move_to_end(snapshot.definition_hash)
            return cached
        if len(_compiled_cache) >= _COMPILED_CACHE_LIMIT:
            _compiled_cache.popitem(last=False)
        _compiled_cache[snapshot.definition_hash] = compiled
    return compiled


def strategy_warmup_bars(strategy: QuantStrategyConfig | StrategySnapshot) -> int:
    snapshot = (
        strategy
        if isinstance(strategy, StrategySnapshot)
        else get_strategy_registry().resolve(strategy.type, strategy.version, strategy.parameters)
    )
    return _compile_cached(snapshot).warmup_bars(snapshot.parameters)


def _commission(amount: float, execution: QuantExecutionConfig) -> float:
    return float(max(amount * execution.commission_rate, execution.minimum_commission))


def _scheduled_rate(
    schedule: tuple[tuple[str, float], ...],
    current_date: str,
) -> float:
    """按 ``(生效起始日, 费率)`` 档期表取出 ``current_date`` 当日适用的费率。

    档期按生效日倒序排列；日期早于最早一档时说明该时段不在支持范围内。
    """
    for effective_from, rate in schedule:
        if current_date >= effective_from:
            return rate
    raise ValueError(f"历史费率仅支持 {A_SHARE_HISTORICAL_FEE_START} 之后的沪深 A 股")


def _trade_fee(
    amount: float, side: str, execution: QuantExecutionConfig, current_date: str | None = None,
) -> float:
    transfer_rate = execution.transfer_fee_rate
    stamp_rate = execution.stamp_duty_rate
    if execution.fee_schedule == "a_share_historical" and current_date is not None:
        transfer_rate = _scheduled_rate(_TRANSFER_FEE_SCHEDULE, current_date)
        stamp_rate = _scheduled_rate(_STAMP_DUTY_SCHEDULE, current_date)
    return float(_commission(amount, execution) + amount * (transfer_rate + (stamp_rate if side == "sell" else 0)))


def _fill_price(
    item: KlineItem, side: str, execution: QuantExecutionConfig, shares: int = 0,
) -> float:
    slippage_bps = execution.slippage_bps
    if execution.slippage_model == "square_root" and item.amount > 0 and shares > 0:
        order_amount = shares * item.open
        impact_bps = execution.market_impact_coefficient * math.sqrt(order_amount / max(item.amount, 1.0))
        slippage_bps += impact_bps
    sign = 1 if side == "buy" else -1
    return float(min(item.high, max(item.low, item.open * (1 + sign * slippage_bps / 10_000))))


def _fill_capacity(
    code: str, item: KlineItem, price: float, state: _PortfolioState, execution: QuantExecutionConfig,
) -> int:
    if state.turnover_date != item.date:
        state.turnover_date = item.date
        state.daily_turnover.clear()
    if execution.max_daily_participation_rate is None:
        return 10**18
    # amount 统一为元，避免不同行情源的 volume 股/手单位差异。
    notional = max(0, item.amount * execution.max_daily_participation_rate - state.daily_turnover.get(code, 0))
    return int(notional / price / execution.lot_size) * execution.lot_size


def _affordable_shares(
    desired: int, price: float, cash: float, execution: QuantExecutionConfig, current_date: str | None = None,
) -> int:
    low, high = 0, desired // execution.lot_size
    while low < high:
        middle = (low + high + 1) // 2
        amount = middle * execution.lot_size * price
        if amount + _trade_fee(amount, "buy", execution, current_date) <= cash:
            low = middle
        else:
            high = middle - 1
    return low * execution.lot_size


def _valid_bar(item: KlineItem) -> bool:
    return (
        all(math.isfinite(value) for value in (item.open, item.high, item.low, item.close, item.volume, item.amount))
        and item.volume >= 0 and item.amount >= 0
        and 0 < item.low <= min(item.open, item.close) <= max(item.open, item.close) <= item.high
        and (item.pre_close is None or (math.isfinite(item.pre_close) and item.pre_close >= 0))
    )


def _validate_stock_bars(code: str, items: list[KlineItem]) -> None:
    previous_date = ""
    for item in items:
        if not _valid_bar(item) or item.date <= previous_date or (item.code and item.code != code):
            raise ValueError(f"{code} {item.date} 行情异常：需有限有效价格、非负成交量额及严格递增日期")
        previous_date = item.date


def _is_tradeable(item: KlineItem, side: str) -> bool:
    if not _valid_bar(item) or item.volume <= 0:
        return False
    one_price = math.isclose(item.open, item.high) and math.isclose(item.open, item.low)
    if one_price:
        # pre_close 缺失时按一字板保守处理：双向拒单，避免跌停误买入/涨停误卖出
        if item.pre_close in (None, 0):
            return False
        if side == "buy" and item.open > item.pre_close:
            return False
        if side == "sell" and item.open < item.pre_close:
            return False
    return True


def _daily_returns(values: list[float]) -> list[float]:
    return [values[index] / values[index - 1] - 1 for index in range(1, len(values)) if values[index - 1] > 0]


def _aligned_returns(points: list[QuantEquityPoint], initial_cash: float) -> tuple[list[float], list[float]]:
    strategy_returns: list[float] = []
    benchmark_returns: list[float] = []
    baseline = QuantEquityPoint(date="", equity=initial_cash, benchmark=initial_cash, drawdown=0)
    for previous, current in zip([baseline, *points], points):
        if (
            previous.equity <= 0
            or previous.benchmark is None
            or current.benchmark is None
            or previous.benchmark <= 0
        ):
            continue
        strategy_returns.append(current.equity / previous.equity - 1)
        benchmark_returns.append(current.benchmark / previous.benchmark - 1)
    return strategy_returns, benchmark_returns


def _annualized_return(total_return: float, observations: int) -> float:
    if observations <= 0 or total_return <= -1:
        return total_return
    return float((1 + total_return) ** (TRADING_DAYS_PER_YEAR / observations) - 1)


def _percent(value: float) -> float:
    return round(value * 100, 6)


def _monthly_returns(points: list[QuantEquityPoint], initial_cash: float) -> list[QuantMonthlyReturn]:
    month_values: dict[str, list[float]] = defaultdict(list)
    for point in points:
        month_values[point.date[:7]].append(point.equity)
    result = []
    previous_close = initial_cash
    for month in sorted(month_values):
        values = month_values[month]
        month_return = values[-1] / previous_close - 1 if previous_close else 0
        result.append(QuantMonthlyReturn(month=month, return_pct=_percent(month_return)))
        previous_close = values[-1]
    return result


def _closed_position_pnls(trades: list[QuantTrade]) -> list[float]:
    holdings: dict[str, int] = defaultdict(int)
    realized: dict[str, float] = defaultdict(float)
    closed = []
    for trade in trades:
        if trade.side == "buy":
            holdings[trade.code] += trade.shares
        else:
            holdings[trade.code] -= trade.shares
            realized[trade.code] += trade.realized_pnl or 0
            if holdings[trade.code] == 0:
                closed.append(realized.pop(trade.code))
    return closed


@dataclass(slots=True)
class _RoundTripStats:
    pnls: list[float]
    holding_days: list[int]
    return_pcts: list[float]
    win_holding_days: list[int]
    loss_holding_days: list[int]
    win_pnls: list[float]
    loss_pnls: list[float]


def _analyze_closed_trades(trades: list[QuantTrade]) -> _RoundTripStats:
    batches: dict[str, list[list[Any]]] = defaultdict(list)
    pnls: list[float] = []
    holding_days_list: list[int] = []
    return_pcts: list[float] = []
    win_holding_days: list[int] = []
    loss_holding_days: list[int] = []
    win_pnls: list[float] = []
    loss_pnls: list[float] = []

    for trade in trades:
        if trade.side == "buy":
            batches[trade.code].append([trade.date, trade.shares, trade.price + (trade.fee / max(trade.shares, 1))])
        else:
            remaining = trade.shares
            sell_dt = None
            if trade.date:
                try:
                    sell_dt = date.fromisoformat(trade.date)
                except (ValueError, TypeError):
                    sell_dt = None
            round_trip_cost = 0.0
            round_trip_proceeds = trade.price * trade.shares - trade.fee
            earliest_buy_dt = None

            while remaining > 0 and batches[trade.code]:
                batch = batches[trade.code][0]
                b_date_str, b_shares, b_cost = batch[0], batch[1], batch[2]
                if earliest_buy_dt is None and b_date_str:
                    try:
                        earliest_buy_dt = date.fromisoformat(b_date_str)
                    except (ValueError, TypeError):
                        earliest_buy_dt = None
                matched = min(remaining, b_shares)
                round_trip_cost += matched * b_cost
                remaining -= matched
                batch[1] -= matched
                if batch[1] <= 0:
                    batches[trade.code].pop(0)

            pnl = trade.realized_pnl if trade.realized_pnl is not None else (round_trip_proceeds - round_trip_cost)
            pnls.append(pnl)

            days = (sell_dt - earliest_buy_dt).days if (sell_dt and earliest_buy_dt) else 1
            days = max(1, days)
            holding_days_list.append(days)

            ret_pct = (pnl / round_trip_cost * 100) if round_trip_cost > 0 else 0.0
            return_pcts.append(ret_pct)

            if pnl > 0:
                win_holding_days.append(days)
                win_pnls.append(pnl)
            elif pnl < 0:
                loss_holding_days.append(days)
                loss_pnls.append(pnl)

    return _RoundTripStats(
        pnls=pnls,
        holding_days=holding_days_list,
        return_pcts=return_pcts,
        win_holding_days=win_holding_days,
        loss_holding_days=loss_holding_days,
        win_pnls=win_pnls,
        loss_pnls=loss_pnls,
    )



HISTORICAL_STRESS_PERIODS: tuple[tuple[str, str, str], ...] = (
    ("2024微盘挤兑", "2024-01-02", "2024-02-08"),
    ("2022单边下行", "2022-01-04", "2022-10-31"),
    ("2018去杠杆熊市", "2018-01-02", "2018-12-28"),
    ("2016熔断踩踏", "2016-01-04", "2016-01-29"),
    ("2015杠杆股灾", "2015-06-15", "2015-08-26"),
)


def _probabilistic_sharpe_ratio(
    returns: list[float],
    sharpe: float | None,
    risk_free_rate: float,
    benchmark_sharpe: float = 0.0,
) -> float | None:
    if sharpe is None or len(returns) < 15:
        return None
    n = len(returns)
    mean_r = statistics.fmean(returns)
    diffs = [r - mean_r for r in returns]
    var_r = statistics.pvariance(returns)
    if var_r <= 1e-12:
        return None
    std_r = math.sqrt(var_r)
    skew = sum(d**3 for d in diffs) / (n * (std_r**3)) if std_r > 0 else 0.0
    kurt = sum(d**4 for d in diffs) / (n * (std_r**4)) if std_r > 0 else 3.0
    sr_daily = sharpe / math.sqrt(TRADING_DAYS_PER_YEAR)
    denom = 1.0 - skew * sr_daily + ((kurt - 1.0) / 4.0) * (sr_daily**2)
    if denom <= 0:
        return None
    se_sr = math.sqrt(denom / (n - 1))
    z = (sr_daily - benchmark_sharpe / math.sqrt(TRADING_DAYS_PER_YEAR)) / se_sr
    psr = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return round(psr * 100, 2)


def _compute_stress_tests(points: list[QuantEquityPoint]) -> dict[str, dict[str, float]] | None:
    if not points:
        return None
    result: dict[str, dict[str, float]] = {}
    for name, start, end in HISTORICAL_STRESS_PERIODS:
        pts = [p for p in points if start <= p.date <= end]
        if len(pts) < 5:
            continue
        p_start, p_end = pts[0], pts[-1]
        period_return = (p_end.equity / p_start.equity - 1) if p_start.equity > 0 else 0.0
        peak = pts[0].equity
        max_dd = 0.0
        for pt in pts:
            if pt.equity > peak:
                peak = pt.equity
            dd = (pt.equity - peak) / peak if peak > 0 else 0.0
            if dd < max_dd:
                max_dd = dd
        result[name] = {
            "return_pct": _percent(period_return),
            "max_drawdown_pct": _percent(max_dd),
        }
    return result if result else None


def _max_drawdown_duration(points: list[QuantEquityPoint]) -> int:
    if len(points) <= 1:
        return 0
    max_duration = 0
    current_duration = 0
    peak = points[0].equity
    for pt in points:
        if pt.equity >= peak:
            peak = pt.equity
            current_duration = 0
        else:
            current_duration += 1
            if current_duration > max_duration:
                max_duration = current_duration
    return max_duration


def _omega_ratio(returns: list[float], threshold: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    gains = sum(max(0.0, r - threshold) for r in returns)
    losses = sum(max(0.0, threshold - r) for r in returns)
    if losses <= 1e-12:
        return 99.0 if gains > 0 else 1.0
    return round(gains / losses, 4)


def _build_metrics(
    points: list[QuantEquityPoint],
    trades: list[QuantTrade],
    initial_cash: float,
    risk_free_rate: float,
) -> QuantMetrics:
    equities = [point.equity for point in points]
    total_return = equities[-1] / initial_cash - 1 if equities else 0
    returns = _daily_returns([initial_cash, *equities])
    daily_volatility = statistics.pstdev(returns) if len(returns) > 1 else 0
    volatility = daily_volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
    excess_daily = (statistics.fmean(returns) - risk_free_rate / TRADING_DAYS_PER_YEAR) if returns else 0
    sharpe = excess_daily / daily_volatility * math.sqrt(TRADING_DAYS_PER_YEAR) if daily_volatility > 0 else None
    downside_returns = [min(value - risk_free_rate / TRADING_DAYS_PER_YEAR, 0) for value in returns]
    downside_daily = (
        math.sqrt(statistics.fmean(value * value for value in downside_returns))
        if len(downside_returns) > 1
        else 0
    )
    downside_volatility = downside_daily * math.sqrt(TRADING_DAYS_PER_YEAR) if downside_daily > 0 else None
    sortino = excess_daily / downside_daily * math.sqrt(TRADING_DAYS_PER_YEAR) if downside_daily > 0 else None
    annualized_return = _annualized_return(total_return, len(equities))
    max_drawdown = min((point.drawdown for point in points), default=0)
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else None
    strategy_returns, benchmark_returns = _aligned_returns(points, initial_cash)
    active_returns = [
        strategy_return - benchmark_return
        for strategy_return, benchmark_return in zip(strategy_returns, benchmark_returns)
    ]
    active_daily_volatility = statistics.pstdev(active_returns) if len(active_returns) > 1 else None
    tracking_error = (
        active_daily_volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
        if active_daily_volatility is not None
        else None
    )
    information_ratio = (
        statistics.fmean(active_returns) / active_daily_volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
        if active_daily_volatility is not None and active_daily_volatility > 0
        else None
    )
    realized = _closed_position_pnls(trades)
    trade_stats = _analyze_closed_trades(trades)
    wins = [value for value in realized if value > 0]
    losses = [value for value in realized if value < 0]
    win_rate = len(wins) / len(realized) if realized else None
    profit_loss_ratio = (
        statistics.fmean(wins) / abs(statistics.fmean(losses)) if wins and losses else None
    )
    avg_holding_days = round(statistics.fmean(trade_stats.holding_days), 1) if trade_stats.holding_days else None
    avg_win_holding_days = round(statistics.fmean(trade_stats.win_holding_days), 1) if trade_stats.win_holding_days else None
    avg_loss_holding_days = round(statistics.fmean(trade_stats.loss_holding_days), 1) if trade_stats.loss_holding_days else None
    avg_win_pnl = round(statistics.fmean(trade_stats.win_pnls), 2) if trade_stats.win_pnls else None
    avg_loss_pnl = round(statistics.fmean(trade_stats.loss_pnls), 2) if trade_stats.loss_pnls else None
    max_win_pct = round(max(trade_stats.return_pcts), 2) if trade_stats.return_pcts else None
    max_loss_pct = round(min(trade_stats.return_pcts), 2) if trade_stats.return_pcts else None
    average_equity = statistics.fmean(equities) if equities else initial_cash
    turnover = sum(trade.amount for trade in trades) / average_equity if average_equity else 0
    # 不把覆盖不足的基准误当作完整回测区间收益。
    final_benchmark = points[-1].benchmark if points else None
    benchmark_return = (
        final_benchmark / initial_cash - 1
        if final_benchmark is not None and all(point.benchmark is not None for point in points)
        else None
    )
    beta = None
    alpha = None
    treynor = None
    upside_capture = None
    downside_capture = None
    if len(benchmark_returns) >= 10:
        b_var = statistics.pvariance(benchmark_returns)
        if b_var > 1e-12:
            s_mean = statistics.fmean(strategy_returns)
            b_mean = statistics.fmean(benchmark_returns)
            cov = sum((s - s_mean) * (b - b_mean) for s, b in zip(strategy_returns, benchmark_returns)) / len(strategy_returns)
            beta_val = cov / b_var
            beta = round(beta_val, 4)
            if benchmark_return is not None:
                ann_b_return = _annualized_return(benchmark_return, len(equities))
                alpha_val = annualized_return - (risk_free_rate + beta_val * (ann_b_return - risk_free_rate))
                alpha = _percent(alpha_val)
            if beta_val > 0.001:
                treynor = round((annualized_return - risk_free_rate) / beta_val, 4)

        up_s = [s for s, b in zip(strategy_returns, benchmark_returns) if b > 0]
        up_b = [b for b in benchmark_returns if b > 0]
        if up_b and statistics.fmean(up_b) > 1e-6:
            upside_capture = _percent(statistics.fmean(up_s) / statistics.fmean(up_b))

        down_s = [s for s, b in zip(strategy_returns, benchmark_returns) if b < 0]
        down_b = [b for b in benchmark_returns if b < 0]
        if down_b and abs(statistics.fmean(down_b)) > 1e-6:
            downside_capture = _percent(statistics.fmean(down_s) / statistics.fmean(down_b))

    drawdown_duration = _max_drawdown_duration(points)
    omega = _omega_ratio(returns, risk_free_rate / TRADING_DAYS_PER_YEAR)
    psr = _probabilistic_sharpe_ratio(returns, sharpe, risk_free_rate)
    # 基于 Lopez de Prado (2014) DSR 模型：校正 10 次多重假设检验偏差
    dsr_benchmark = 0.5 * math.sqrt(2.0 * math.log(10))
    dsr = _probabilistic_sharpe_ratio(returns, sharpe, risk_free_rate, benchmark_sharpe=dsr_benchmark)

    allocation_effect = None
    selection_effect = None
    interaction_effect = None
    if benchmark_return is not None and points:
        equity_weights = []
        for p in points:
            if p.equity > 0:
                pos_val = p.positions_value if p.positions_value is not None else max(0.0, p.equity - (p.cash or 0.0))
                equity_weights.append(max(0.0, min(1.0, pos_val / p.equity)))
            else:
                equity_weights.append(0.0)
        avg_w_e = statistics.fmean(equity_weights) if equity_weights else 0.0
        avg_w_c = 1.0 - avg_w_e
        rf_cum = (1.0 + risk_free_rate) ** (len(points) / TRADING_DAYS_PER_YEAR) - 1.0
        if avg_w_e > 0.01:
            r_pe = (total_return - avg_w_c * rf_cum) / avg_w_e
        else:
            r_pe = benchmark_return
        a_eff = avg_w_c * (rf_cum - benchmark_return)
        s_eff = r_pe - benchmark_return
        i_eff = (avg_w_e - 1.0) * s_eff
        allocation_effect = _percent(a_eff)
        selection_effect = _percent(s_eff)
        interaction_effect = _percent(i_eff)

    return QuantMetrics(
        total_return=_percent(total_return),
        annualized_return=_percent(annualized_return),
        benchmark_return=_percent(benchmark_return) if benchmark_return is not None else None,
        excess_return=_percent(total_return - benchmark_return) if benchmark_return is not None else None,
        annualized_volatility=_percent(volatility),
        downside_volatility=_percent(downside_volatility) if downside_volatility is not None else None,
        sharpe_ratio=round(sharpe, 6) if sharpe is not None else None,
        sortino_ratio=round(sortino, 6) if sortino is not None else None,
        calmar_ratio=round(calmar, 6) if calmar is not None else None,
        tracking_error=_percent(tracking_error) if tracking_error is not None else None,
        information_ratio=round(information_ratio, 6) if information_ratio is not None else None,
        alpha=alpha,
        beta=beta,
        treynor_ratio=treynor,
        upside_capture=upside_capture,
        downside_capture=downside_capture,
        max_drawdown=_percent(max_drawdown),
        max_drawdown_duration_days=drawdown_duration,
        omega_ratio=omega,
        win_rate=_percent(win_rate) if win_rate is not None else None,
        profit_loss_ratio=round(profit_loss_ratio, 6) if profit_loss_ratio is not None else None,
        turnover_rate=_percent(turnover),
        trade_count=len(trades),
        closed_trade_count=len(realized),
        observation_count=len(points),
        avg_holding_days=avg_holding_days,
        avg_win_holding_days=avg_win_holding_days,
        avg_loss_holding_days=avg_loss_holding_days,
        avg_win_pnl=avg_win_pnl,
        avg_loss_pnl=avg_loss_pnl,
        max_win_pct=max_win_pct,
        max_loss_pct=max_loss_pct,
        probabilistic_sharpe_ratio=psr,
        deflated_sharpe_ratio=dsr,
        allocation_effect=allocation_effect,
        selection_effect=selection_effect,
        interaction_effect=interaction_effect,
        stress_tests=_compute_stress_tests(points),
    )


def _update_execution_targets(
    current_date: str,
    bars_by_code: dict[str, list[KlineItem]],
    date_indexes: dict[str, dict[str, int]],
    targets: dict[str, list[int | float]],
    previous_targets: dict[str, int | float],
    execution_targets: dict[str, int | float],
) -> bool:
    changed = False
    for code in bars_by_code:
        index = date_indexes[code].get(current_date)
        if index is None or index == 0:
            continue
        execution_targets[code] = targets[code][index - 1]
        changed = changed or not math.isclose(float(execution_targets[code]), float(previous_targets[code]))
        previous_targets[code] = execution_targets[code]
    return changed


def _allocation_prices(
    codes: Iterable[str],
    available_bars: dict[str, KlineItem],
    state: _PortfolioState,
) -> dict[str, float]:
    return {
        code: available_bars[code].open
        if code in available_bars and available_bars[code].open > 0
        else state.last_prices.get(code, state.average_cost[code])
        for code in codes
    }


def _calculate_inverse_volatility_weights(
    active_codes: list[str],
    bars_by_code: dict[str, list[KlineItem]],
    current_date: str = "",
    date_indexes: dict[str, dict[str, int]] | None = None,
    lookback: int = 20,
) -> dict[str, float]:
    if not active_codes:
        return {}
    if len(active_codes) == 1:
        return {active_codes[0]: 1.0}

    inv_vols: dict[str, float] = {}
    valid_invs: list[float] = []

    for code in active_codes:
        items = bars_by_code.get(code, [])
        if not items:
            continue
        if date_indexes and code in date_indexes and current_date:
            idx = date_indexes[code].get(current_date)
            history = items[max(0, idx - lookback - 1):idx] if idx is not None else items[-lookback - 1:]
        elif current_date:
            history = [item for item in items if item.date < current_date][-lookback - 1:]
        else:
            history = items[-lookback - 1:]

        if len(history) >= 5:
            closes = [item.close for item in history if item.close > 0]
            if len(closes) >= 5:
                returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
                vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
                if vol > 1e-6:
                    inv = 1.0 / vol
                    inv_vols[code] = inv
                    valid_invs.append(inv)

    default_inv = statistics.fmean(valid_invs) if valid_invs else 1.0
    for code in active_codes:
        if code not in inv_vols:
            inv_vols[code] = default_inv

    total_inv = sum(inv_vols.values())
    if total_inv <= 0:
        return {code: 1.0 / len(active_codes) for code in active_codes}
    return {code: inv_vols[code] / total_inv for code in active_codes}


def _is_rebalance_date(current_date: str, previous_date: str | None, frequency: str) -> bool:
    if frequency == "daily" or previous_date is None:
        return True
    try:
        curr_dt = date.fromisoformat(current_date)
        prev_dt = date.fromisoformat(previous_date)
        if frequency == "weekly":
            return curr_dt.isocalendar()[:2] != prev_dt.isocalendar()[:2]
        if frequency == "monthly":
            return (curr_dt.year, curr_dt.month) != (prev_dt.year, prev_dt.month)
    except (ValueError, TypeError):
        return True
    return True


def _calculate_cross_sectional_scores(
    active_codes: list[str],
    bars_by_code: dict[str, list[KlineItem]],
    current_date: str = "",
    date_indexes: dict[str, dict[str, int]] | None = None,
    metric: str = "momentum",
    lookback: int = 20,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for code in active_codes:
        items = bars_by_code.get(code, [])
        if not items:
            scores[code] = 0.0
            continue
        if date_indexes and code in date_indexes and current_date:
            idx = date_indexes[code].get(current_date)
            history = items[max(0, idx - lookback):idx] if idx is not None else items[-lookback:]
        elif current_date:
            history = [item for item in items if item.date < current_date][-lookback:]
        else:
            history = items[-lookback:]

        if metric == "momentum":
            closes = [item.close for item in history if item.close > 0]
            scores[code] = (closes[-1] - closes[0]) / closes[0] if len(closes) >= 2 else 0.0
        elif metric == "inverse_volatility":
            closes = [item.close for item in history if item.close > 0]
            if len(closes) >= 5:
                returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
                vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
                scores[code] = (1.0 / vol) if vol > 1e-6 else 1.0
            else:
                scores[code] = 1.0
        elif metric == "turnover":
            amounts = [item.amount for item in history if item.amount > 0]
            scores[code] = statistics.fmean(amounts) if amounts else 0.0
        else:
            scores[code] = 0.0
    return scores


def _build_desired_shares(
    codes: dict[str, list[KlineItem]],
    execution_targets: dict[str, int | float],
    allocation_prices: dict[str, float],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
    current_date: str = "",
    date_indexes: dict[str, dict[str, int]] | None = None,
) -> tuple[list[str], dict[str, int]]:
    active_codes = [code for code, target in execution_targets.items() if target > 0]
    if execution.top_n_selection is not None and len(active_codes) > execution.top_n_selection:
        if execution.ranking_metric != "equal":
            scores = _calculate_cross_sectional_scores(
                active_codes,
                codes,
                current_date=current_date,
                date_indexes=date_indexes,
                metric=execution.ranking_metric,
                lookback=execution.ranking_lookback,
            )
            ranked = sorted(active_codes, key=lambda c: (-scores.get(c, 0.0), c))
            selected = set(ranked[:execution.top_n_selection])
        else:
            selected = set(sorted(active_codes)[:execution.top_n_selection])

        for code in list(active_codes):
            if code not in selected:
                execution_targets[code] = 0
        active_codes = [c for c in active_codes if c in selected]

    open_equity = state.cash + sum(
        state.holdings[code] * allocation_prices.get(code, state.average_cost[code])
        for code in state.holdings
    )
    is_weighted = any(isinstance(target, float) and 0 < target < 1 for target in execution_targets.values())
    if execution.allocation_method == "risk_parity" and len(active_codes) > 1:
        rp_weights = _calculate_inverse_volatility_weights(
            active_codes, codes, current_date=current_date, date_indexes=date_indexes
        )
        if is_weighted:
            raw_weights = {
                c: float(execution_targets[c]) * rp_weights.get(c, 1.0 / len(active_codes))
                for c in active_codes
            }
            total = sum(raw_weights.values())
            normalized_weights = {c: raw_weights[c] / total for c in active_codes} if total > 0 else rp_weights
        else:
            normalized_weights = rp_weights
    elif is_weighted:
        total_target_weight = sum(max(0.0, float(execution_targets[c])) for c in active_codes)
        normalized_weights = {
            c: (float(execution_targets[c]) / total_target_weight if total_target_weight > 1.0 else float(execution_targets[c]))
            for c in active_codes
        }
    else:
        weight = min(
            execution.max_position_weight,
            (1 - execution.cash_reserve_ratio) * state.risk_scale / len(active_codes),
        ) if active_codes else 0
        normalized_weights = {c: weight for c in active_codes}

    desired_shares = {}
    for code in codes:
        reference_price = allocation_prices.get(code)
        if execution_targets[code] > 0 and reference_price:
            w = min(
                execution.max_position_weight,
                normalized_weights[code] * (1 - execution.cash_reserve_ratio) * state.risk_scale,
            )
            target_value = open_equity * w
            desired_shares[code] = int(target_value / reference_price / execution.lot_size) * execution.lot_size
        else:
            desired_shares[code] = 0
    return active_codes, desired_shares


def _risk_limits_exceeded(
    allocation_prices: dict[str, float], state: _PortfolioState, execution: QuantExecutionConfig,
) -> bool:
    values = {code: shares * allocation_prices[code] for code, shares in state.holdings.items()}
    invested = sum(values.values())
    equity = state.cash + invested
    if execution.max_position_weight < 1 and any(
        value > equity * execution.max_position_weight + 1e-8 for value in values.values()
    ):
        return True
    return execution.cash_reserve_ratio > 0 and state.cash < equity * execution.cash_reserve_ratio - 1e-8


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
        price = _fill_price(available_bars[code], "sell", execution, shares=shares)
        shares = min(shares, _fill_capacity(code, available_bars[code], price, state, execution))
        if shares <= 0:
            continue
        amount = price * shares
        fee = _trade_fee(amount, "sell", execution, current_date)
        state.daily_turnover[code] = state.daily_turnover.get(code, 0) + amount
        realized_pnl = (price - state.average_cost[code]) * shares - fee
        state.cash += amount - fee
        state.holdings[code] -= shares
        if state.holdings[code] == 0:
            state.average_cost[code] = 0
            state.holding_highs.pop(code, None)
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
    allocation_prices: dict[str, float],
    desired_shares: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> None:
    # 现金不足时按缺口市值降序买入，同市值按代码升序，避免 universe 顺序偏差；
    # 全程确定，同一输入永远得到同一成交序列
    def shortfall_value(code: str) -> tuple[float, str]:
        shares = desired_shares[code] - state.holdings[code]
        reference_price = allocation_prices.get(code) or 0.0
        return (-max(shares, 0) * reference_price, code)

    for code in sorted(active_codes, key=shortfall_value):
        shares = desired_shares[code] - state.holdings[code]
        if shares <= 0 or code not in available_bars or not _is_tradeable(available_bars[code], "buy"):
            continue
        price = _fill_price(available_bars[code], "buy", execution, shares=shares)
        shares = min(shares, _fill_capacity(code, available_bars[code], price, state, execution))
        open_equity = state.cash + sum(
            quantity * allocation_prices.get(key, state.average_cost[key]) for key, quantity in state.holdings.items()
        )
        spendable_cash = max(0, state.cash - open_equity * execution.cash_reserve_ratio)
        shares = _affordable_shares(shares, price, spendable_cash, execution, current_date)
        if shares <= 0:
            continue
        amount = price * shares
        fee = _trade_fee(amount, "buy", execution, current_date)
        state.daily_turnover[code] = state.daily_turnover.get(code, 0) + amount
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
    allocation_prices: dict[str, float],
    execution_targets: dict[str, int | float],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
    date_indexes: dict[str, dict[str, int]] | None = None,
) -> tuple[bool, dict[str, _DeferredIntent]]:
    active_codes, desired_shares = _build_desired_shares(
        bars_by_code,
        execution_targets,
        allocation_prices,
        state,
        execution,
        current_date=current_date,
        date_indexes=date_indexes,
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
        allocation_prices,
        desired_shares,
        state,
        execution,
    )
    _, remaining_desired_shares = _build_desired_shares(
        bars_by_code,
        execution_targets,
        allocation_prices,
        state,
        execution,
        current_date=current_date,
        date_indexes=date_indexes,
    )
    retryable_now, blocked = _classify_unresolved_rebalance(
        bars_by_code,
        available_bars,
        allocation_prices,
        execution_targets,
        remaining_desired_shares,
        state,
        execution,
    )
    return retryable_now, blocked


def _required_trade_side(
    code: str,
    target: int | float,
    desired_shares: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> Literal["buy", "sell"] | None:
    difference = desired_shares[code] - state.holdings[code]
    if difference >= execution.lot_size:
        return "buy"
    if difference <= -execution.lot_size:
        return "sell"
    if target > 0 and state.holdings[code] == 0:
        return "buy"
    return None


def _can_buy_lot(
    item: KlineItem,
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> bool:
    price = _fill_price(item, "buy", execution, shares=execution.lot_size)
    amount = price * execution.lot_size
    return bool(amount + _trade_fee(amount, "buy", execution, item.date) <= state.cash)


def _classify_unresolved_rebalance(
    codes: Iterable[str],
    available_bars: dict[str, KlineItem],
    allocation_prices: dict[str, float],
    execution_targets: dict[str, int | float],
    desired_shares: dict[str, int],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
) -> tuple[bool, dict[str, _DeferredIntent]]:
    retryable_now = False
    deferred: dict[str, _DeferredIntent] = {}
    for code in codes:
        side = _required_trade_side(
            code,
            execution_targets[code],
            desired_shares,
            state,
            execution,
        )
        if side is None:
            continue
        item = available_bars.get(code)
        retryable_now = True
        if item is None or not _is_tradeable(item, side):
            deferred[code] = _DeferredIntent(target=execution_targets[code], side=side)
        elif _fill_capacity(code, item, _fill_price(item, side, execution), state, execution) < execution.lot_size:
            deferred[code] = _DeferredIntent(target=execution_targets[code], side=side)
        elif side == "buy" and (
            desired_shares[code] < execution.lot_size
            or not _can_buy_lot(item, state, execution)
        ):
            deferred[code] = _DeferredIntent(target=execution_targets[code], side=side)
    return retryable_now, deferred


def _retry_deferred_buys(
    current_date: str,
    bars_by_code: dict[str, list[KlineItem]],
    available_bars: dict[str, KlineItem],
    allocation_prices: dict[str, float],
    execution_targets: dict[str, int | float],
    deferred_intents: dict[str, _DeferredIntent],
    state: _PortfolioState,
    execution: QuantExecutionConfig,
    date_indexes: dict[str, dict[str, int]] | None = None,
) -> None:
    active_codes, desired_shares = _build_desired_shares(
        bars_by_code,
        execution_targets,
        allocation_prices,
        state,
        execution,
        current_date=current_date,
        date_indexes=date_indexes,
    )
    wakeable: list[str] = []
    for code in sorted(deferred_intents):
        intent = deferred_intents[code]
        if intent.side != "buy":
            continue
        if execution_targets[code] != intent.target or execution_targets[code] <= 0:
            del deferred_intents[code]
            continue
        shortfall = desired_shares[code] - state.holdings[code]
        if shortfall < execution.lot_size:
            if state.holdings[code] > 0:
                del deferred_intents[code]
            continue
        item = available_bars.get(code)
        if item is None or not _is_tradeable(item, "buy") or not _can_buy_lot(item, state, execution):
            continue
        wakeable.append(code)

    if not wakeable:
        return
    active_order = [code for code in active_codes if code in wakeable]
    _buy_shortfall_positions(
        current_date,
        active_order,
        available_bars,
        allocation_prices,
        desired_shares,
        state,
        execution,
    )
    _, remaining_desired = _build_desired_shares(
        bars_by_code,
        execution_targets,
        allocation_prices,
        state,
        execution,
        current_date=current_date,
        date_indexes=date_indexes,
    )
    for code in wakeable:
        if state.holdings[code] > 0 and remaining_desired[code] - state.holdings[code] < execution.lot_size:
            deferred_intents.pop(code, None)


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
    positions_value = sum(
        state.holdings[code] * state.last_prices.get(code, state.average_cost[code])
        for code in state.holdings
    )
    equity = state.cash + positions_value
    state.peak_equity = max(state.peak_equity, equity)
    benchmark_value = None
    if benchmark_start and current_date in benchmark_map:
        benchmark_value = execution.initial_cash * benchmark_map[current_date] / benchmark_start

    position_weights: dict[str, float] = {}
    if equity > 0:
        for code, shares in state.holdings.items():
            if shares > 0:
                pos_val = shares * state.last_prices.get(code, state.average_cost[code])
                position_weights[code] = round(pos_val / equity, 4)
        position_weights["CASH"] = round(max(0.0, state.cash) / equity, 4)

    return QuantEquityPoint(
        date=current_date,
        equity=round(equity, 2),
        benchmark=round(benchmark_value, 2) if benchmark_value is not None else None,
        drawdown=equity / state.peak_equity - 1 if state.peak_equity else 0,
        cash=round(state.cash, 2),
        positions_value=round(positions_value, 2),
        position_weights=position_weights,
    )


def _enrich_points_with_rolling_metrics(
    points: list[QuantEquityPoint],
    initial_cash: float,
    risk_free_rate: float,
    window: int = 60,
) -> None:
    if not points or initial_cash <= 0:
        return
    equities = [p.equity for p in points]
    strategy_returns = _daily_returns([initial_cash, *equities])

    valid_benchmarks = [p.benchmark for p in points if p.benchmark is not None]
    has_benchmark = len(valid_benchmarks) == len(points)
    benchmark_returns = _daily_returns([initial_cash, *valid_benchmarks]) if has_benchmark else []

    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR

    for i, pt in enumerate(points):
        if pt.benchmark is not None and initial_cash > 0:
            pt.excess_return = round((pt.equity / initial_cash - pt.benchmark / initial_cash) * 100, 2)

        if i >= window - 1 and len(strategy_returns) > i:
            sub_strat = strategy_returns[i - window + 1 : i + 1]
            stdev_s = statistics.pstdev(sub_strat)
            if stdev_s > 1e-12:
                mean_s = statistics.fmean(sub_strat)
                pt.rolling_sharpe = round((mean_s - rf_daily) / stdev_s * math.sqrt(TRADING_DAYS_PER_YEAR), 2)

            if has_benchmark and len(benchmark_returns) > i:
                sub_bench = benchmark_returns[i - window + 1 : i + 1]
                var_b = statistics.pvariance(sub_bench)
                if var_b > 1e-12:
                    mean_b = statistics.fmean(sub_bench)
                    mean_s = statistics.fmean(sub_strat)
                    cov = sum((s - mean_s) * (b - mean_b) for s, b in zip(sub_strat, sub_bench)) / len(sub_strat)
                    pt.rolling_beta = round(cov / var_b, 2)


def _volatility_scale(
    bars_by_code: dict[str, list[KlineItem]], date_indexes: dict[str, dict[str, int]],
    current_date: str, targets: dict[str, int | float], target_volatility: float | None,
) -> float:
    if target_volatility is None:
        return 1.0
    active = [code for code, target in targets.items() if target > 0]
    if not active:
        return 1.0
    daily_by_code = []
    reference_dates = None
    for code in active:
        index = date_indexes[code].get(current_date)
        if index is None or index < 21:
            return 0.0  # 不足 20 个历史收益样本时不冒充零波动。
        history = bars_by_code[code][index - 21:index]
        dates = [item.date for item in history]
        if reference_dates is not None and dates != reference_dates:
            return 0.0  # 不把停牌跨日收益与其他股票的单日收益按位置拼接。
        reference_dates = dates
        values = [item.close for item in history]
        if any(not math.isfinite(value) or value <= 0 for value in values):
            return 0.0
        daily_by_code.append(_daily_returns(values))

    total_w = sum(float(targets[c]) for c in active)
    if total_w > 0 and daily_by_code and len(daily_by_code[0]) > 0:
        portfolio_returns = [
            sum(float(targets[code]) * daily_by_code[i][day_idx] for i, code in enumerate(active)) / total_w
            for day_idx in range(len(daily_by_code[0]))
        ]
    else:
        portfolio_returns = [statistics.fmean(day) for day in zip(*daily_by_code)]
    volatility = statistics.pstdev(portfolio_returns) * math.sqrt(TRADING_DAYS_PER_YEAR)
    return min(1.0, target_volatility / volatility) if volatility > 0 else 1.0


def _update_risk_at_close(
    available_bars: dict[str, KlineItem], state: _PortfolioState, execution: QuantExecutionConfig,
    point: QuantEquityPoint, raw_targets: dict[str, int | float],
) -> None:
    for code, shares in state.holdings.items():
        if shares <= 0:
            if raw_targets[code] <= 0:
                state.stopped_codes.discard(code)
            continue
        item = available_bars.get(code)
        if item is None:
            continue
        high = max(state.holding_highs.get(code, item.high), item.high)
        state.holding_highs[code] = high
        stop_loss = execution.stop_loss_pct
        trailing = execution.trailing_stop_pct
        if (
            (stop_loss is not None and item.close <= state.average_cost[code] * (1 - stop_loss))
            or (trailing is not None and item.close <= high * (1 - trailing))
        ):
            state.stopped_codes.add(code)
    if execution.max_portfolio_drawdown is not None and point.drawdown <= -execution.max_portfolio_drawdown:
        state.drawdown_halted = True


def _run_backtest_once(
    bars_by_code: dict[str, list[KlineItem]],
    benchmark_items: list[KlineItem],
    strategy: QuantStrategyConfig | StrategySnapshot,
    execution: QuantExecutionConfig,
    *,
    data_hashes: list[str],
    data_sources: list[str],
    evaluation_start_date: str | None = None,
    evaluation_end_date: str | None = None,
    cancel_event: threading.Event | None = None,
) -> QuantBacktestResult:
    _check_cancelled(cancel_event)
    if not bars_by_code:
        raise ValueError("股票池没有可用行情")
    for code, items in bars_by_code.items():
        _check_cancelled(cancel_event)
        _validate_stock_bars(code, items)
    for item in benchmark_items:
        if not math.isfinite(item.close) or item.close <= 0:
            raise ValueError(f"基准 {item.date} 行情收盘价异常")
    bar_maps = {code: {item.date: item for item in items} for code, items in bars_by_code.items()}
    date_indexes = {
        code: {item.date: index for index, item in enumerate(items)}
        for code, items in bars_by_code.items()
    }
    targets = {}
    for code, items in bars_by_code.items():
        _check_cancelled(cancel_event)
        targets[code] = build_target_positions(items, strategy, evaluation_start_date=evaluation_start_date)
    previous_targets: dict[str, int | float] = {code: 0 for code in bars_by_code}
    execution_targets: dict[str, int | float] = {code: 0 for code in bars_by_code}
    state = _PortfolioState(
        cash=execution.initial_cash,
        holdings={code: 0 for code in bars_by_code},
        average_cost={code: 0.0 for code in bars_by_code},
        peak_equity=execution.initial_cash,
    )
    points: list[QuantEquityPoint] = []
    stock_dates = {
        item.date
        for items in bars_by_code.values()
        for item in items
        if (evaluation_start_date is None or item.date >= evaluation_start_date)
        and (evaluation_end_date is None or item.date <= evaluation_end_date)
    }
    if not stock_dates:
        raise ValueError("回测区间没有共同交易数据")
    benchmark_map = {item.date: item.close for item in benchmark_items}
    stock_start, stock_end = min(stock_dates), max(stock_dates)
    benchmark_dates = {day for day in benchmark_map if stock_start <= day <= stock_end}
    all_dates = sorted(stock_dates | benchmark_dates)
    first_benchmark = next((item for item in benchmark_items if item.date == all_dates[0]), None)
    prior_benchmark = max(
        (item for item in benchmark_items if item.date < all_dates[0]), key=lambda item: item.date, default=None,
    )
    # 首日收益从昨收计起；无昨收和前置数据时仅使用当日开盘价，不虚构前一交易日。
    benchmark_start = (
        first_benchmark.pre_close or (prior_benchmark.close if prior_benchmark else first_benchmark.open)
        if first_benchmark else None
    )
    if benchmark_start is not None and (not math.isfinite(benchmark_start) or benchmark_start <= 0):
        raise ValueError("基准起始价格异常")
    if evaluation_start_date is not None:
        for code, items in bars_by_code.items():
            prior_close = next(
                (item.close for item in reversed(items) if item.date < evaluation_start_date),
                None,
            )
            if prior_close is not None:
                state.last_prices[code] = prior_close

    rebalance_days_remaining = 0
    deferred_intents: dict[str, _DeferredIntent] = {}

    last_effective_targets = dict(execution_targets)
    previous_trading_date: str | None = None
    for current_date in all_dates:
        _check_cancelled(cancel_event)
        available_bars = {code: bar_maps[code][current_date] for code in bars_by_code if current_date in bar_maps[code]}
        is_rebalance = _is_rebalance_date(current_date, previous_trading_date, execution.rebalance_frequency)
        previous_trading_date = current_date

        if is_rebalance:
            _update_execution_targets(
                current_date,
                bars_by_code,
                date_indexes,
                targets,
                previous_targets,
                execution_targets,
            )
        else:
            for code in bars_by_code:
                idx = date_indexes[code].get(current_date)
                if idx is not None and idx > 0:
                    previous_targets[code] = targets[code][idx - 1]

        for code in execution_targets:
            if state.drawdown_halted or code in state.stopped_codes:
                execution_targets[code] = 0
        risk_scale = _volatility_scale(
            bars_by_code, date_indexes, current_date, execution_targets, execution.target_annual_volatility,
        )
        targets_changed = execution_targets != last_effective_targets or not math.isclose(risk_scale, state.risk_scale)
        state.risk_scale = risk_scale
        last_effective_targets = dict(execution_targets)
        allocation_prices = _allocation_prices(bars_by_code, available_bars, state)
        _, desired_shares = _build_desired_shares(
            bars_by_code,
            execution_targets,
            allocation_prices,
            state,
            execution,
            current_date=current_date,
            date_indexes=date_indexes,
        )
        periodic_rebalance_trigger = is_rebalance and execution.rebalance_frequency != "daily"
        if targets_changed or _risk_limits_exceeded(allocation_prices, state, execution) or periodic_rebalance_trigger:
            deferred_intents.clear()
            rebalance_days_remaining = execution.rebalance_window_days
        else:
            resumed_sell = False
            for code, intent in list(deferred_intents.items()):
                if execution_targets[code] != intent.target:
                    del deferred_intents[code]
                    continue
                if intent.side != "sell":
                    continue
                side = _required_trade_side(
                    code,
                    execution_targets[code],
                    desired_shares,
                    state,
                    execution,
                )
                if side != "sell":
                    del deferred_intents[code]
                    continue
                item = available_bars.get(code)
                if item is not None and _is_tradeable(item, "sell"):
                    del deferred_intents[code]
                    resumed_sell = True
            if resumed_sell:
                rebalance_days_remaining = execution.rebalance_window_days

        # last_prices 始终为最近收盘价（_build_equity_point 收盘时更新），
        # allocation_prices 则使用同一时点的开盘价做目标仓位计算。

        if rebalance_days_remaining > 0:
            retryable_now, deferred_intents = _rebalance_portfolio(
                current_date,
                bars_by_code,
                available_bars,
                allocation_prices,
                execution_targets,
                state,
                execution,
                date_indexes=date_indexes,
            )
            rebalance_days_remaining = rebalance_days_remaining - 1 if retryable_now else 0
        elif deferred_intents:
            _retry_deferred_buys(
                current_date,
                bars_by_code,
                available_bars,
                allocation_prices,
                execution_targets,
                deferred_intents,
                state,
                execution,
                date_indexes=date_indexes,
            )

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

        _update_risk_at_close(available_bars, state, execution, points[-1], previous_targets)

    if not points:
        raise ValueError("回测区间没有共同交易数据")
    _enrich_points_with_rolling_metrics(points, execution.initial_cash, execution.risk_free_rate)
    combined_hash = hashlib.sha256(
        json.dumps(sorted(data_hashes), separators=(",", ":")).encode()
    ).hexdigest()
    return QuantBacktestResult(
        model_assumptions=[
            "信号收盘生成、下一交易日开盘撮合；日线不能模拟盘口排队或开盘时可知的成交量。",
            "成交价按滑点后限制在当日高低价内；参与率按全天成交额估算，不代表真实开盘成交能力。",
            "相同引擎版本和输入快照可复现；前复权行情用于信号、成交和估值，未模拟现金分红、送转股及复权因子变化。",
            "仓位与现金约束按每日开盘估值尝试纠偏，盘中波动或成交受限仍可超限。",
            "执行风控基于实际持仓成本及持仓后最高价，收盘触发、次日尝试退出；回撤熔断后本次回测不再开仓。",
            "后段验证使用固定参数和独立初始资金，不代表策略未见过该样本，也不构成统计显著性证明。",
        ],
        engine_version=ENGINE_VERSION,
        data_hash=combined_hash,
        data_sources=sorted(set(data_sources)),
        codes=sorted(bars_by_code),
        metrics=_build_metrics(points, state.trades, execution.initial_cash, execution.risk_free_rate),
        equity_curve=points,
        monthly_returns=_monthly_returns(points, execution.initial_cash),
        trades=state.trades,
        open_positions=[
            QuantOpenPosition(
                code=code,
                shares=shares,
                average_cost=round(state.average_cost[code], 4),
                last_price=round(state.last_prices.get(code, state.average_cost[code]), 4),
                market_value=round(shares * state.last_prices.get(code, state.average_cost[code]), 2),
                unrealized_pnl=round(
                    shares * (state.last_prices.get(code, state.average_cost[code]) - state.average_cost[code]),
                    2,
                ),
            )
            for code, shares in sorted(state.holdings.items())
            if shares > 0
        ],
    )


def _holdout_start_date(trading_dates: list[str]) -> tuple[str, int] | None:
    total = len(trading_dates)
    if total < MIN_TRAINING_OBSERVATIONS + MIN_HOLDOUT_OBSERVATIONS:
        return None
    split_index = round(total * HOLDOUT_TRAINING_RATIO)
    split_index = max(MIN_TRAINING_OBSERVATIONS, split_index)
    split_index = min(total - MIN_HOLDOUT_OBSERVATIONS, split_index)
    return trading_dates[split_index], split_index


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
    cancel_event: threading.Event | None = None,
) -> QuantBacktestResult:
    result = _run_backtest_once(
        bars_by_code,
        benchmark_items,
        strategy,
        execution,
        data_hashes=data_hashes,
        data_sources=data_sources,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
        cancel_event=cancel_event,
    )
    # 只按实际评估日切分，预热行情和结束日后的数据不能扩大验证样本。
    holdout_split = _holdout_start_date([point.date for point in result.equity_curve])
    if holdout_split is None:
        return result
    holdout_start_date, training_observations = holdout_split
    holdout_result = _run_backtest_once(
        bars_by_code,
        benchmark_items,
        strategy,
        execution,
        data_hashes=data_hashes,
        data_sources=data_sources,
        evaluation_start_date=holdout_start_date,
        evaluation_end_date=result.equity_curve[-1].date,
        cancel_event=cancel_event,
    )
    result.holdout_validation = QuantHoldoutValidation(
        training_ratio=training_observations / len(result.equity_curve),
        start_date=holdout_start_date,
        end_date=holdout_result.equity_curve[-1].date,
        observation_count=len(holdout_result.equity_curve),
        metrics=holdout_result.metrics,
    )
    return result
