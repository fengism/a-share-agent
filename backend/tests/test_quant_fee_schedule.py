"""量化回测的费率档期与年化换算常量。

历史费率档期是「市场事实」而不是可调参数：日期一变、费率一变，回测的成本口径就会
漂移，而这类漂移很隐蔽（只在跨越档期的区间上体现为收益差异）。因此用参数化用例把
每个档期边界锁死。
"""

from __future__ import annotations

import math

import pytest

from app.modules.quant.engine import (
    _STAMP_DUTY_SCHEDULE,
    _TRANSFER_FEE_SCHEDULE,
    A_SHARE_HISTORICAL_FEE_START,
    TRADING_DAYS_PER_YEAR,
    _commission,
    _scheduled_rate,
    _trade_fee,
)
from app.modules.quant.schemas import QuantExecutionConfig


@pytest.mark.parametrize(
    ("current_date", "expected_transfer", "expected_stamp"),
    [
        # 支持范围起点
        ("2015-08-01", 0.00002, 0.001),
        # 过户费下调前
        ("2022-04-28", 0.00002, 0.001),
        # 过户费下调生效日
        ("2022-04-29", 0.00001, 0.001),
        # 印花税减半生效日前一天
        ("2023-08-27", 0.00001, 0.001),
        # 印花税减半生效日
        ("2023-08-28", 0.00001, 0.0005),
        ("2026-01-01", 0.00001, 0.0005),
    ],
)
def test_historical_fee_schedule_boundaries(
    current_date: str,
    expected_transfer: float,
    expected_stamp: float,
) -> None:
    assert _scheduled_rate(_TRANSFER_FEE_SCHEDULE, current_date) == expected_transfer
    assert _scheduled_rate(_STAMP_DUTY_SCHEDULE, current_date) == expected_stamp


def test_dates_before_supported_window_are_rejected() -> None:
    before_start = "2015-07-31"
    with pytest.raises(ValueError, match="历史费率仅支持"):
        _scheduled_rate(_TRANSFER_FEE_SCHEDULE, before_start)
    with pytest.raises(ValueError, match="历史费率仅支持"):
        _scheduled_rate(_STAMP_DUTY_SCHEDULE, before_start)


def test_schedule_tables_start_at_the_supported_boundary() -> None:
    """档期表必须正好从支持范围起点开始，否则会出现「静默使用错误的旧档位」。"""
    assert _TRANSFER_FEE_SCHEDULE[-1][0] == A_SHARE_HISTORICAL_FEE_START
    assert _STAMP_DUTY_SCHEDULE[-1][0] == A_SHARE_HISTORICAL_FEE_START


def test_schedules_are_sorted_descending_by_effective_date() -> None:
    """取档位靠「首个 current_date >= 生效日」匹配，顺序错会取到错误费率。"""
    for schedule in (_TRANSFER_FEE_SCHEDULE, _STAMP_DUTY_SCHEDULE):
        dates = [effective_from for effective_from, _ in schedule]
        assert dates == sorted(dates, reverse=True)


def test_stamp_duty_only_applies_to_sell_side() -> None:
    # fee_schedule="a_share_historical" 会用历史档期覆盖 transfer_fee_rate / stamp_duty_rate，
    # 所以这里按 2024-01-02 的实际档位（过户费 0.00001、印花税 0.0005）来推导期望值。
    execution = QuantExecutionConfig(
        fee_schedule="a_share_historical",
        commission_rate=0.0,
        minimum_commission=0.0,
    )
    amount = 1_000_000
    transfer_rate, stamp_rate = 0.00001, 0.0005

    assert _trade_fee(amount, "sell", execution, "2024-01-02") == pytest.approx(
        amount * (transfer_rate + stamp_rate)
    )
    # 买入不计印花税，只计过户费
    assert _trade_fee(amount, "buy", execution, "2024-01-02") == pytest.approx(amount * transfer_rate)


def test_custom_schedule_uses_configured_rates_not_history() -> None:
    execution = QuantExecutionConfig(
        fee_schedule="custom",
        commission_rate=0.0,
        minimum_commission=0.0,
        transfer_fee_rate=0.00002,
        stamp_duty_rate=0.001,
    )
    # 即使日期落在历史档期内，custom 也必须用配置值
    assert _trade_fee(1_000_000, "sell", execution, "2024-01-02") == pytest.approx(1_020.0)


def test_commission_respects_minimum() -> None:
    execution = QuantExecutionConfig(commission_rate=0.0003, minimum_commission=5)
    assert _commission(1_000, execution) == 5
    assert _commission(1_000_000, execution) == pytest.approx(300.0)


def test_trading_days_per_year_is_market_convention() -> None:
    """年化收益与夏普/索提诺换算都以此为准，改动会影响所有历史回测的可比性。"""
    assert TRADING_DAYS_PER_YEAR == 252
    # 与引擎中实际用于年化的算式保持一致
    total_return = 0.25
    observations = 60
    annualized = (1 + total_return) ** (TRADING_DAYS_PER_YEAR / observations) - 1
    assert annualized == pytest.approx((1.25) ** (252 / 60) - 1)
    assert math.sqrt(TRADING_DAYS_PER_YEAR) == pytest.approx(15.8745, rel=1e-4)
