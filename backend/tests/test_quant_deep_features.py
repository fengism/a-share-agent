"""量化策略深度优化特性测试：包括扩展数据字段、高阶指标算子、连续仓位模型与专业风控指标。"""

from __future__ import annotations

import pytest

from app.domain.market import KlineItem
from app.modules.quant.engine import (
    _compute_stress_tests,
    _max_drawdown_duration,
    _omega_ratio,
    _probabilistic_sharpe_ratio,
    run_backtest,
    strategy_warmup_bars,
)
from app.modules.quant.schemas import (
    QuantEquityPoint,
    QuantExecutionConfig,
    QuantStrategyConfig,
    QuantUniverse,
)
from app.modules.quant.strategies.compiler import compile_strategy
from app.modules.quant.strategies.contracts import (
    StrategyDefinition,
    StrategyIndicatorDefinition,
    StrategyParameterDefinition,
    StrategyPositionDefinition,
    StrategySignalExpression,
    StrategySignals,
    StrategySnapshot,
)
from app.modules.quant.strategies.evaluator import evaluate_target_positions
from app.modules.quant.strategies.registry import get_strategy_registry


def _make_bar(
    date: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1_000_000.0,
    amount: float = 50_000_000.0,
    turnover_pct: float = 2.5,
    amplitude: float = 3.0,
    change_pct: float = 1.0,
    code: str = "600519",
) -> KlineItem:
    return KlineItem(
        code=code,
        date=date,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        turnover_pct=turnover_pct,
        amplitude=amplitude,
        change_pct=change_pct,
        pre_close=open_,
    )


def test_universe_expanded_limit() -> None:
    # 允许最多 30 只股票
    codes = [f"6000{i:02d}" for i in range(30)]
    universe = QuantUniverse(source="custom", codes=codes)
    assert len(universe.codes) == 30

    # 超过 30 只股票报错
    with pytest.raises(Exception):
        QuantUniverse(source="custom", codes=[f"6000{i:02d}" for i in range(31)])


def test_data_fields_support_turnover_and_amount() -> None:
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="turnover_test",
        version="1.0.0",
        name="换手测试",
        description="基于换手率与成交额过滤",
        scenario="震荡",
        risk_level="low",
        parameters={
            "min_turnover": StrategyParameterDefinition(
                type="number", label="最低换手", default=2.0
            ),
        },
        indicators={
            "turnover_ma": StrategyIndicatorDefinition(
                operator="sma",
                input="turnover_pct",
                period=3,
            ),
            "amount_ma": StrategyIndicatorDefinition(
                operator="sma",
                input="amount",
                period=3,
            ),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(
                operator="greater_than",
                left="turnover_pct",
                right="$min_turnover",
            ),
            exit=StrategySignalExpression(
                operator="less_than",
                left="turnover_pct",
                right="$min_turnover",
            ),
        ),
    )
    compiled = compile_strategy(definition)
    bars = [
        _make_bar("2024-01-02", 100, 105, 95, 102, turnover_pct=1.0),
        _make_bar("2024-01-03", 102, 106, 101, 105, turnover_pct=3.0),
        _make_bar("2024-01-04", 105, 108, 103, 107, turnover_pct=2.5),
        _make_bar("2024-01-05", 107, 109, 104, 106, turnover_pct=1.5),
    ]
    targets = evaluate_target_positions(bars, compiled, {"min_turnover": 2.0})
    assert targets == [0, 1, 1, 0]


def test_atr_and_momentum_indicators() -> None:
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="atr_momentum_test",
        version="1.0.0",
        name="ATR与动量测试",
        description="测试 ATR 与动量算子",
        scenario="趋势",
        risk_level="medium",
        parameters={},
        indicators={
            "volatility_atr": StrategyIndicatorDefinition(
                operator="atr",
                period=5,
            ),
            "price_mom": StrategyIndicatorDefinition(
                operator="momentum",
                input="close",
                period=5,
            ),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(
                operator="greater_than",
                left="price_mom",
                right=0,
            ),
            exit=StrategySignalExpression(
                operator="less_than",
                left="price_mom",
                right=0,
            ),
        ),
    )
    compiled = compile_strategy(definition)
    bars = [
        _make_bar(f"2024-01-{i:02d}", 100 + i, 102 + i, 99 + i, 101 + i)
        for i in range(1, 15)
    ]
    targets = evaluate_target_positions(bars, compiled, {})
    assert len(targets) == len(bars)
    # 动量全为正，第 6 根 bar 之后入场为 1
    assert targets[6] == 1


def test_continuous_weight_mode() -> None:
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="continuous_test",
        version="1.0.0",
        name="连续仓位测试",
        description="半仓持仓",
        scenario="震荡",
        risk_level="low",
        parameters={},
        indicators={
            "ma5": StrategyIndicatorDefinition(
                operator="sma",
                input="close",
                period=3,
            ),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(
                operator="greater_than",
                left="close",
                right="ma5",
            ),
            exit=StrategySignalExpression(
                operator="less_than",
                left="close",
                right="ma5",
            ),
        ),
        position=StrategyPositionDefinition(
            mode="continuous_weight",
            target_weight=0.5,
        ),
    )
    compiled = compile_strategy(definition)
    bars = [
        _make_bar("2024-01-02", 100, 101, 99, 100),
        _make_bar("2024-01-03", 100, 102, 98, 100),
        _make_bar("2024-01-04", 100, 105, 99, 104),  # close=104 > ma5(101.33)
        _make_bar("2024-01-05", 104, 106, 103, 105),
        _make_bar("2024-01-08", 105, 105, 95, 96),   # close=96 < ma5(101.66)
    ]
    targets = evaluate_target_positions(bars, compiled, {})
    # 触发 entry 时仓位权重为 0.5
    assert targets[2] == 0.5
    assert targets[3] == 0.5
    assert targets[4] == 0


def test_probabilistic_sharpe_ratio_and_stress_tests() -> None:
    # 构造标准收益率样本
    returns = [0.01, -0.005, 0.015, -0.002, 0.008, 0.012, -0.004, 0.009, 0.003, -0.001, 0.006, 0.007, -0.003, 0.011, 0.005, 0.002]
    psr = _probabilistic_sharpe_ratio(returns, sharpe=1.8, risk_free_rate=0.015)
    assert psr is not None
    assert 50.0 < psr <= 100.0

    # 构造覆盖 2024 微盘挤兑区间的净值曲线
    points = [
        QuantEquityPoint(date="2024-01-02", equity=1000000, drawdown=0),
        QuantEquityPoint(date="2024-01-10", equity=980000, drawdown=-0.02),
        QuantEquityPoint(date="2024-01-20", equity=960000, drawdown=-0.04),
        QuantEquityPoint(date="2024-01-30", equity=940000, drawdown=-0.06),
        QuantEquityPoint(date="2024-02-05", equity=930000, drawdown=-0.07),
        QuantEquityPoint(date="2024-02-08", equity=950000, drawdown=-0.05),
    ]
    stress = _compute_stress_tests(points)
    assert stress is not None
    assert "2024微盘挤兑" in stress
    assert stress["2024微盘挤兑"]["return_pct"] < 0


def test_run_backtest_with_continuous_weight() -> None:
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="half_weight_test",
        version="1.0.0",
        name="半仓回测测试",
        description="半仓持仓",
        scenario="趋势",
        risk_level="low",
        parameters={},
        indicators={
            "ma2": StrategyIndicatorDefinition(
                operator="sma",
                input="close",
                period=2,
            ),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(
                operator="greater_than",
                left="close",
                right="ma2",
            ),
            exit=StrategySignalExpression(
                operator="less_than",
                left="close",
                right="ma2",
            ),
        ),
        position=StrategyPositionDefinition(
            mode="continuous_weight",
            target_weight=0.5,
        ),
    )
    snapshot = StrategySnapshot(
        key="half_weight_test",
        version="1.0.0",
        definition_hash="sha256:" + "a" * 64,
        parameters={},
        definition=definition,
    )
    bars = [
        _make_bar("2024-01-02", 100, 102, 98, 100),
        _make_bar("2024-01-03", 100, 103, 99, 102),  # ma2=101, close=102 > ma2 -> buy signal for next bar
        _make_bar("2024-01-04", 102, 105, 101, 104), # next bar open 102, executes buy ~50%
        _make_bar("2024-01-05", 104, 106, 103, 105),
        _make_bar("2024-01-08", 105, 105, 95, 96),   # exit
        _make_bar("2024-01-09", 96, 98, 94, 95),
    ]
    benchmark_bars = [
        _make_bar(bar.date, 3000, 3050, 2980, 3010) for bar in bars
    ]
    execution = QuantExecutionConfig(initial_cash=1_000_000, max_position_weight=1.0)
    result = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=execution,
        data_hashes=["hash1"],
        data_sources=["test"],
    )
    assert result.trades, "应产生交易"
    buy_trade = result.trades[0]
    assert buy_trade.side == "buy"
    # 验证仓位市值接近 50%（500,000 元），而不是全仓 1,000,000
    assert 450_000 <= buy_trade.amount <= 550_000
    assert result.metrics.probabilistic_sharpe_ratio is not None or result.metrics.observation_count < 15


def test_risk_parity_allocation() -> None:
    # 构造两只股票历史：A 为高波动股（日涨跌幅 ~4%），B 为低波动稳健股（日涨跌幅 ~0.5%）
    dates = [
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08",
        "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12", "2024-01-15",
        "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19", "2024-01-22",
        "2024-01-23", "2024-01-24", "2024-01-25", "2024-01-26", "2024-01-29",
        "2024-01-30", "2024-01-31",
    ]
    bars_a = []
    bars_b = []
    p_a = 100.0
    p_b = 100.0
    for i, d in enumerate(dates):
        # A 剧烈震荡
        p_a = p_a * (1.04 if i % 2 == 0 else 0.96)
        # B 平缓微幅震荡
        p_b = p_b * (1.005 if i % 2 == 0 else 0.995)
        bars_a.append(_make_bar(d, p_a, p_a * 1.01, p_a * 0.99, p_a, code="000001"))
        bars_b.append(_make_bar(d, p_b, p_b * 1.002, p_b * 0.998, p_b, code="000002"))

    benchmark_bars = [_make_bar(d, 3000, 3010, 2990, 3000, code="000300") for d in dates]

    # 双均线策略产生买入信号
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="rp_test",
        version="1.0.0",
        name="风险平价策略",
        description="全持仓",
        scenario="趋势",
        risk_level="low",
        parameters={},
        indicators={
            "c_sma": StrategyIndicatorDefinition(operator="sma", input="close", period=1),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(operator="greater_than", left="close", right=0),
            exit=StrategySignalExpression(operator="less_than", left="close", right=0),
        ),
    )
    snapshot = StrategySnapshot(
        key="rp_test",
        version="1.0.0",
        definition_hash="sha256:" + "b" * 64,
        parameters={},
        definition=definition,
    )

    # 1. 等权分配 (allocation_method="equal")
    exec_equal = QuantExecutionConfig(
        initial_cash=1_000_000,
        allocation_method="equal",
    )
    res_equal = run_backtest(
        bars_by_code={"000001": bars_a, "000002": bars_b},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=exec_equal,
        data_hashes=["h1", "h2"],
        data_sources=["test"],
        evaluation_start_date="2024-01-16",
    )
    buys_equal = {t.code: t.amount for t in res_equal.trades if t.side == "buy"}
    assert len(buys_equal) == 2
    # 等权分配下，两只股票买入金额几乎相等（各约 500,000 元）
    assert abs(buys_equal["000001"] - buys_equal["000002"]) < 30_000

    # 2. 风险平价分配 (allocation_method="risk_parity")
    exec_rp = QuantExecutionConfig(
        initial_cash=1_000_000,
        allocation_method="risk_parity",
    )
    res_rp = run_backtest(
        bars_by_code={"000001": bars_a, "000002": bars_b},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=exec_rp,
        data_hashes=["h1", "h2"],
        data_sources=["test"],
        evaluation_start_date="2024-01-16",
    )
    # 在具备历史波动样本后，低波动的 000002 权重应显著大于高波动的 000001
    buys_rp = {t.code: t.amount for t in res_rp.trades if t.side == "buy"}
    assert len(buys_rp) == 2
    assert buys_rp["000002"] > buys_rp["000001"] * 2.0, "低波动股票应获得更大配比以平衡风险贡献"


def test_rebalance_frequency_weekly_and_monthly() -> None:
    # 构造 30 个交易日数据
    dates = [
        # 第 1 周
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
        # 第 2 周
        "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12",
        # 第 3 周
        "2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19",
        # 第 4 周
        "2024-01-22", "2024-01-23", "2024-01-24", "2024-01-25", "2024-01-26",
        # 跨月第 5 周
        "2024-01-29", "2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02",
    ]
    # 价格交替穿透 MA2，造成频繁买卖切换
    bars = []
    for i, d in enumerate(dates):
        c = 105.0 if i % 2 == 1 else 95.0
        bars.append(_make_bar(d, 100.0, 110.0, 90.0, c))

    benchmark_bars = [_make_bar(d, 3000, 3010, 2990, 3000) for d in dates]

    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="churn_test",
        version="1.0.0",
        name="频繁假突破策略",
        description="频繁买卖",
        scenario="趋势",
        risk_level="high",
        parameters={},
        indicators={
            "ma2": StrategyIndicatorDefinition(operator="sma", input="close", period=2),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(operator="greater_than", left="close", right="ma2"),
            exit=StrategySignalExpression(operator="less_than", left="close", right="ma2"),
        ),
    )
    snapshot = StrategySnapshot(
        key="churn_test",
        version="1.0.0",
        definition_hash="sha256:" + "c" * 64,
        parameters={},
        definition=definition,
    )

    # 1. 每日调仓 (rebalance_frequency="daily")
    res_daily = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=QuantExecutionConfig(initial_cash=1_000_000, rebalance_frequency="daily"),
        data_hashes=["h1"],
        data_sources=["test"],
    )
    # 2. 每周调仓 (rebalance_frequency="weekly")
    res_weekly = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=QuantExecutionConfig(initial_cash=1_000_000, rebalance_frequency="weekly"),
        data_hashes=["h1"],
        data_sources=["test"],
    )
    # 3. 每月调仓 (rebalance_frequency="monthly")
    res_monthly = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=QuantExecutionConfig(initial_cash=1_000_000, rebalance_frequency="monthly"),
        data_hashes=["h1"],
        data_sources=["test"],
    )

    # 周频与月频有效过滤日间假突破与无序轮动，大幅降低交易换手与摩擦损耗
    assert len(res_daily.trades) > len(res_weekly.trades)
    assert len(res_weekly.trades) >= len(res_monthly.trades)

    # 验证周频交易日期只发生在每周初
    weekly_trade_dates = {t.date for t in res_weekly.trades}
    for d in weekly_trade_dates:
        # 必须是周初日期之一
        assert d in {"2024-01-03", "2024-01-08", "2024-01-15", "2024-01-22", "2024-01-29"}


def test_square_root_slippage_model() -> None:
    # 测试平方根市场冲击模型：大单比小单面临更高的市场冲击与滑点
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    # 限制单日成交额为 10,000,000 元
    bars = [
        _make_bar("2024-01-02", 100, 105, 95, 102, amount=10_000_000.0),
        _make_bar("2024-01-03", 100, 105, 95, 102, amount=10_000_000.0),
        _make_bar("2024-01-04", 100, 105, 95, 102, amount=10_000_000.0),
    ]
    benchmark_bars = [_make_bar(d, 3000, 3010, 2990, 3000) for d in dates]

    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="slippage_test",
        version="1.0.0",
        name="滑点测试",
        description="全持仓",
        scenario="趋势",
        risk_level="low",
        parameters={},
        indicators={
            "c_sma": StrategyIndicatorDefinition(operator="sma", input="close", period=1),
        },
        signals=StrategySignals(
            entry=StrategySignalExpression(operator="greater_than", left="close", right=0),
            exit=StrategySignalExpression(operator="less_than", left="close", right=0),
        ),
    )
    snapshot = StrategySnapshot(
        key="slippage_test",
        version="1.0.0",
        definition_hash="sha256:" + "d" * 64,
        parameters={},
        definition=definition,
    )

    # 1. 固定滑点 (fixed 5 bps = 0.05%)
    res_fixed = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=QuantExecutionConfig(
            initial_cash=1_000_000,
            slippage_bps=5,
            slippage_model="fixed",
        ),
        data_hashes=["h1"],
        data_sources=["test"],
    )
    price_fixed = res_fixed.trades[0].price

    # 2. 平方根冲击滑点 (square_root, base 5 bps, impact coeff 50.0)
    res_impact = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=benchmark_bars,
        strategy=snapshot,
        execution=QuantExecutionConfig(
            initial_cash=1_000_000,
            slippage_bps=5,
            slippage_model="square_root",
            market_impact_coefficient=50.0,
        ),
        data_hashes=["h1"],
        data_sources=["test"],
    )
    price_impact = res_impact.trades[0].price

    # 冲击模型下买入价格更高（滑点更大）
    assert price_impact > price_fixed


def test_advanced_risk_metrics() -> None:
    # 1. 测试最大回撤修复期（最长水下持续天数）
    points = [
        QuantEquityPoint(date="2024-01-02", equity=100.0, drawdown=0.0),
        QuantEquityPoint(date="2024-01-03", equity=95.0, drawdown=-0.05),  # 水下第 1 天
        QuantEquityPoint(date="2024-01-04", equity=90.0, drawdown=-0.10),  # 水下第 2 天
        QuantEquityPoint(date="2024-01-05", equity=92.0, drawdown=-0.08),  # 水下第 3 天
        QuantEquityPoint(date="2024-01-08", equity=105.0, drawdown=0.0),   # 修复创新高
        QuantEquityPoint(date="2024-01-09", equity=103.0, drawdown=-0.019), # 水下第 1 天
    ]
    assert _max_drawdown_duration(points) == 3

    # 2. 测试欧米茄比率 (Omega Ratio)
    # 收益多于亏损
    returns = [0.02, 0.01, -0.01, 0.015, -0.005, 0.03]
    omega = _omega_ratio(returns, threshold=0.0)
    assert omega is not None and omega > 1.0

    # 3. 运行回测验证 DSR、Omega 和回撤修复期被完整写入 QuantMetrics
    bars = [
        _make_bar(f"2024-01-{i:02d}", 100 + (i % 3), 105, 95, 102 + (i % 2))
        for i in range(1, 25)
    ]
    bench = [_make_bar(b.date, 3000, 3010, 2990, 3000, code="000300") for b in bars]
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="dsr_test",
        version="1.0.0",
        name="DSR测试",
        description="全持仓",
        scenario="趋势",
        risk_level="low",
        parameters={},
        indicators={"c_sma": StrategyIndicatorDefinition(operator="sma", input="close", period=1)},
        signals=StrategySignals(
            entry=StrategySignalExpression(operator="greater_than", left="close", right=0),
            exit=StrategySignalExpression(operator="less_than", left="close", right=0),
        ),
    )
    snapshot = StrategySnapshot(
        key="dsr_test",
        version="1.0.0",
        definition_hash="sha256:" + "e" * 64,
        parameters={},
        definition=definition,
    )
    res = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=bench,
        strategy=snapshot,
        execution=QuantExecutionConfig(initial_cash=1_000_000),
        data_hashes=["h1"],
        data_sources=["test"],
    )
    assert res.metrics.max_drawdown_duration_days is not None
    assert res.metrics.omega_ratio is not None
    assert res.metrics.deflated_sharpe_ratio is not None
    assert 0.0 <= res.metrics.deflated_sharpe_ratio <= 100.0


def test_low_volatility_trend_preset() -> None:
    registry = get_strategy_registry()
    snapshot = registry.resolve("low_volatility_trend", None, {})
    assert snapshot is not None, "应成功加载低波均线稳健策略模板"
    assert snapshot.definition.api_version == "quant.strategy/v2"
    assert snapshot.definition.position.mode == "continuous_weight"
    assert snapshot.definition.position.target_weight == 0.7

    compiled = compile_strategy(snapshot.definition)
    # 构造平稳上升趋势数据（低波动）
    bars = [
        _make_bar(f"2024-01-{i:02d}", 100 + i * 0.5, 101 + i * 0.5, 99.5 + i * 0.5, 100.5 + i * 0.5)
        for i in range(1, 30)
    ]
    targets = evaluate_target_positions(bars, compiled, snapshot.parameters)
    # 充分预热后，平稳低波上涨应产生 0.7 目标仓位
    assert any(t == 0.7 for t in targets)


def test_capm_and_capture_metrics() -> None:
    # 构造跑赢基准的行情：基准震荡微涨，个股强势上涨
    dates = [f"2024-01-{i:02d}" for i in range(1, 26)]
    bars = []
    bench = []
    p, b = 100.0, 3000.0
    for i, d in enumerate(dates):
        p *= 1.015 if i % 2 == 0 else 0.995
        b *= 1.005 if i % 2 == 0 else 0.998
        bars.append(_make_bar(d, p, p * 1.01, p * 0.99, p))
        bench.append(_make_bar(d, b, b * 1.002, b * 0.998, b, code="000300"))

    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="capm_test",
        version="1.0.0",
        name="CAPM测试",
        description="全持仓",
        scenario="趋势",
        risk_level="low",
        parameters={},
        indicators={"c_sma": StrategyIndicatorDefinition(operator="sma", input="close", period=1)},
        signals=StrategySignals(
            entry=StrategySignalExpression(operator="greater_than", left="close", right=0),
            exit=StrategySignalExpression(operator="less_than", left="close", right=0),
        ),
    )
    snapshot = StrategySnapshot(
        key="capm_test",
        version="1.0.0",
        definition_hash="sha256:" + "f" * 64,
        parameters={},
        definition=definition,
    )
    res = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=bench,
        strategy=snapshot,
        execution=QuantExecutionConfig(initial_cash=1_000_000),
        data_hashes=["h1"],
        data_sources=["test"],
    )
    assert res.metrics.beta is not None, "应计算出 Beta 系数"
    assert res.metrics.alpha is not None, "应计算出 Alpha 超额收益"
    assert res.metrics.treynor_ratio is not None, "应计算出特雷诺比率"
    assert res.metrics.upside_capture is not None, "应计算出上行捕获率"
    assert res.metrics.downside_capture is not None, "应计算出下行捕获率"


def test_volatility_scale_continuous_weight() -> None:
    from app.modules.quant.engine import _volatility_scale
    dates = [f"2024-01-{i:02d}" for i in range(1, 26)]
    bars = [_make_bar(d, 100 + i * 2, 102 + i * 2, 98 + i * 2, 101 + i * 2) for i, d in enumerate(dates)]
    date_indexes = {"600519": {b.date: i for i, b in enumerate(bars)}}
    # 目标仓位为浮点连续权重 0.7
    targets = {"600519": 0.7}
    scale = _volatility_scale(
        bars_by_code={"600519": bars},
        date_indexes=date_indexes,
        current_date=dates[-1],
        targets=targets,
        target_volatility=0.10,
    )
    assert 0.0 < scale <= 1.0, "连续权重目标应正确触发波动率缩放控仓"


def test_cross_sectional_top_n_selection() -> None:
    dates = [f"2024-01-{i:02d}" for i in range(1, 26)]
    # 股票 1: 强动量（从 10 涨到 25）
    bars1 = [_make_bar(d, 10 + i * 0.6, 11 + i * 0.6, 9 + i * 0.6, 10.5 + i * 0.6, code="000001") for i, d in enumerate(dates)]
    # 股票 2: 中动量（从 20 涨到 25）
    bars2 = [_make_bar(d, 20 + i * 0.2, 21 + i * 0.2, 19 + i * 0.2, 20.2 + i * 0.2, code="000002") for i, d in enumerate(dates)]
    # 股票 3: 弱动量/阴跌（从 30 跌到 25）
    bars3 = [_make_bar(d, 30 - i * 0.2, 31 - i * 0.2, 29 - i * 0.2, 29.8 - i * 0.2, code="000003") for i, d in enumerate(dates)]

    bench = [_make_bar(d, 3000, 3010, 2990, 3005, code="000300") for d in dates]

    # 策略：只要收盘价 > 0 就满仓
    definition = StrategyDefinition(
        api_version="quant.strategy/v2",
        key="all_in",
        version="1.0.0",
        name="全入场",
        description="全量买入测试",
        scenario="趋势",
        risk_level="low",
        parameters={},
        indicators={"c_sma": StrategyIndicatorDefinition(operator="sma", input="close", period=1)},
        signals=StrategySignals(
            entry=StrategySignalExpression(operator="greater_than", left="close", right=0),
            exit=StrategySignalExpression(operator="less_than", left="close", right=0),
        ),
    )
    snapshot = StrategySnapshot(
        key="all_in",
        version="1.0.0",
        definition_hash="sha256:" + "a" * 64,
        parameters={},
        definition=definition,
    )

    # 截面优选：Top 2 动量
    res = run_backtest(
        bars_by_code={"000001": bars1, "000002": bars2, "000003": bars3},
        benchmark_items=bench,
        strategy=snapshot,
        execution=QuantExecutionConfig(
            initial_cash=1_000_000,
            top_n_selection=2,
            ranking_metric="momentum",
            ranking_lookback=10,
        ),
        data_hashes=["h1"],
        data_sources=["test"],
        evaluation_start_date=dates[15],
    )

    held_codes = {t.code for t in res.trades if t.side == "buy"}
    assert "000001" in held_codes, "动量最强的 000001 必须被选中"
    assert "000002" in held_codes, "动量次强的 000002 必须被选中"
    assert "000003" not in held_codes, "动量最弱的 000003 不应进入 Top 2 持仓"


@pytest.mark.asyncio
async def test_parameter_sensitivity_scan_flow() -> None:
    import uuid
    from app.infrastructure.persistence import account_store
    from app.modules.quant.persistence import runs as run_store
    from app.modules.quant.schemas import QuantParameterScanRequest
    from app.modules.quant.service import scan_parameter_sensitivity

    dates = [f"2024-01-{i:02d}" for i in range(1, 26)]
    bars = [_make_bar(d, 100 + i, 102 + i, 98 + i, 101 + i, code="600519") for i, d in enumerate(dates)]
    bench = [_make_bar(d, 3000, 3010, 2990, 3005, code="000300") for d in dates]

    # 构造一次完成的持久化回测任务
    user = account_store.create_user(f"scan_{uuid.uuid4().hex[:8]}", "Password123!")
    user_id = int(user["id"])
    base_req = {
        "name": "敏感性测试回测",
        "universe": {"source": "custom", "codes": ["600519"]},
        "strategy": {
            "type": "ma_cross",
            "parameters": {"fast_period": 5, "slow_period": 20},
        },
        "execution": {
            "initial_cash": 1_000_000,
        },
        "start_date": dates[10],
        "end_date": dates[-1],
        "benchmark": "000300",
    }
    input_snapshot = {
        "stocks": {"600519": [b.model_dump(mode="json") for b in bars]},
        "benchmark": [b.model_dump(mode="json") for b in bench],
    }
    row = run_store.create_run(user_id, "敏感性测试回测", base_req)
    # 模拟任务成功完成
    run_store.claim_next("test_worker")
    run_store.complete(
        row.id,
        "test_worker",
        result={"metrics": {"total_return": 5.0, "sharpe_ratio": 1.2}, "engine_version": "test"},
        input_snapshot=input_snapshot,
    )

    scan_req = QuantParameterScanRequest(
        param1_name="fast_period",
        param1_values=[3, 5, 8],
        param2_name="slow_period",
        param2_values=[15, 20],
    )

    result = await scan_parameter_sensitivity(row.id, scan_req, user_id)
    assert len(result.points) == 6, "3x2 网格应产生 6 个评估点"
    assert result.optimal_point is not None
    assert 0 <= result.robustness_score <= 100
    assert 0 <= result.profitable_ratio <= 100


@pytest.mark.asyncio
async def test_parameter_sensitivity_endpoint() -> None:
    import uuid
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    from app.api.auth.dependencies import require_active_user
    from app.infrastructure.persistence import account_store
    from app.modules.quant.persistence import runs as run_store

    user = account_store.create_user(f"api_{uuid.uuid4().hex[:8]}", "Password123!")
    user_id = int(user["id"])
    dates = [f"2024-01-{i:02d}" for i in range(1, 26)]
    bars = [_make_bar(d, 100 + i, 102 + i, 98 + i, 101 + i, code="600519") for i, d in enumerate(dates)]
    bench = [_make_bar(d, 3000, 3010, 2990, 3005, code="000300") for d in dates]

    base_req = {
        "name": "API测试回测",
        "universe": {"source": "custom", "codes": ["600519"]},
        "strategy": {
            "type": "ma_cross",
            "parameters": {"fast_period": 5, "slow_period": 20},
        },
        "execution": {
            "initial_cash": 1_000_000,
        },
        "start_date": dates[10],
        "end_date": dates[-1],
        "benchmark": "000300",
    }
    input_snapshot = {
        "stocks": {"600519": [b.model_dump(mode="json") for b in bars]},
        "benchmark": [b.model_dump(mode="json") for b in bench],
    }
    row = run_store.create_run(user_id, "API测试回测", base_req)
    run_store.claim_next("test_worker")
    run_store.complete(
        row.id,
        "test_worker",
        result={"metrics": {"total_return": 5.0, "sharpe_ratio": 1.2}, "engine_version": "test"},
        input_snapshot=input_snapshot,
    )

    app.dependency_overrides[require_active_user] = lambda: {"id": user_id, "username": user["username"], "is_admin": False}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/quant/backtests/{row.id}/sensitivity-scan",
                json={
                    "param1_name": "fast_period",
                    "param1_values": [3, 5],
                    "param2_name": "slow_period",
                    "param2_values": [15, 20],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["param1_name"] == "fast_period"
            assert len(data["points"]) == 4
            assert data["optimal_point"] is not None
    finally:
        app.dependency_overrides.pop(require_active_user, None)


def test_trade_holding_and_payoff_diagnostics() -> None:
    from app.modules.quant.engine import _analyze_closed_trades
    from app.modules.quant.schemas import QuantTrade

    trades = [
        QuantTrade(date="2024-01-02", code="600519", side="buy", price=100.0, shares=100, amount=10000.0, fee=5.0),
        QuantTrade(date="2024-01-12", code="600519", side="sell", price=120.0, shares=100, amount=12000.0, fee=6.0, realized_pnl=1989.0),
        QuantTrade(date="2024-01-15", code="600519", side="buy", price=120.0, shares=100, amount=12000.0, fee=5.0),
        QuantTrade(date="2024-01-18", code="600519", side="sell", price=110.0, shares=100, amount=11000.0, fee=5.0, realized_pnl=-1010.0),
    ]

    stats = _analyze_closed_trades(trades)
    assert len(stats.holding_days) == 2
    assert stats.holding_days[0] == 10  # 2024-01-02 to 2024-01-12
    assert stats.holding_days[1] == 3   # 2024-01-15 to 2024-01-18
    assert len(stats.win_holding_days) == 1
    assert stats.win_holding_days[0] == 10
    assert len(stats.loss_holding_days) == 1
    assert stats.loss_holding_days[0] == 3
    assert stats.win_pnls[0] == 1989.0
    assert stats.loss_pnls[0] == -1010.0
    assert stats.return_pcts[0] > 15.0
    assert stats.return_pcts[1] < 0.0


def test_holdings_weights_and_rolling_metrics() -> None:
    dates = [f"2024-01-{i:02d}" for i in range(1, 31)] + [f"2024-02-{i:02d}" for i in range(1, 30)] + [f"2024-03-{i:02d}" for i in range(1, 30)]
    bars = [_make_bar(d, 100.0 + i * 0.5, 102.0 + i * 0.5, 99.0 + i * 0.5, 101.0 + i * 0.5) for i, d in enumerate(dates)]
    bench = [_make_bar(d, 3000.0 + i * 2, 3050.0 + i * 2, 2980.0 + i * 2, 3020.0 + i * 2, code="000300") for i, d in enumerate(dates)]

    strat_cfg = QuantStrategyConfig(type="ma_cross", parameters={"fast_period": 5, "slow_period": 10})
    exec_cfg = QuantExecutionConfig(initial_cash=100_000.0)

    result = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=bench,
        strategy=strat_cfg,
        execution=exec_cfg,
        data_hashes=["h"],
        data_sources=["test"],
    )

    assert len(result.equity_curve) == len(dates)
    # Check that position weights and cash are populated
    for pt in result.equity_curve:
        assert pt.cash is not None
        assert pt.positions_value is not None
        assert pt.position_weights is not None
        assert "CASH" in pt.position_weights
        assert pt.excess_return is not None

    # Check that rolling metrics exist after 60 days
    last_pt = result.equity_curve[-1]
    assert last_pt.rolling_sharpe is not None
    assert last_pt.rolling_beta is not None


def test_brinson_fachler_attribution() -> None:
    dates = [f"2024-01-{i:02d}" for i in range(1, 25)]
    bars = [_make_bar(d, 100.0, 110.0 + i * 2, 90.0, 100.0 + i) for i, d in enumerate(dates)]
    bench = [_make_bar(d, 3000.0, 3100.0, 2800.0, 3000.0 - i * 10, code="000300") for i, d in enumerate(dates)]

    strat_cfg = QuantStrategyConfig(type="ma_cross", parameters={"fast_period": 3, "slow_period": 5})
    exec_cfg = QuantExecutionConfig(initial_cash=100_000.0)

    result = run_backtest(
        bars_by_code={"600519": bars},
        benchmark_items=bench,
        strategy=strat_cfg,
        execution=exec_cfg,
        data_hashes=["h"],
        data_sources=["test"],
    )

    assert result.metrics.benchmark_return is not None
    assert result.metrics.excess_return is not None
    assert result.metrics.allocation_effect is not None
    assert result.metrics.selection_effect is not None
    assert result.metrics.interaction_effect is not None
    # Check that the Brinson attribution roughly equals excess return
    brinson_sum = result.metrics.allocation_effect + result.metrics.selection_effect + result.metrics.interaction_effect
    assert abs(brinson_sum - result.metrics.excess_return) < 0.5





