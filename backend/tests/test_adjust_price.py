"""本地仿射复权的价格换算测试：Decimal 复用不得改变任何结果。"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.market_daily.adjustment import _adjust_price, apply_adjustment
from app.modules.market_daily.models import MarketDailyAdjustmentFactor, MarketDailyBar


def _offset(index: int) -> timedelta:
    """用日历偏移近似交易日序列即可，测试只关心换算一致性。"""
    return timedelta(days=index * 7 // 5)


def _bar(trade_date: date, *, close: float, open_: float = 10.0) -> MarketDailyBar:
    now = datetime.now(UTC)
    top = max(open_, close)
    bottom = min(open_, close)
    return MarketDailyBar(
        market="cn",
        instrument_type="stock",
        code="600519",
        trade_date=trade_date,
        currency="CNY",
        open=open_,
        high=top * 1.02,
        low=bottom * 0.98,
        close=close,
        volume=1000,
        amount=1000.0,
        source="test",
        verification_status="confirmed",
        revision=1,
        first_refreshed_at=now,
        last_refreshed_at=now,
    )


def _factor(trade_date: date, mul: float, add: float) -> MarketDailyAdjustmentFactor:
    return MarketDailyAdjustmentFactor(
        code="600519",
        trade_date=trade_date,
        qfq_multiplier=mul,
        qfq_offset=add,
        hfq_multiplier=mul,
        hfq_offset=add,
        action_hash="hash",
        algorithm_version="test",
        calculated_at=datetime.now(UTC),
    )


def test_adjust_price_accepts_float_and_decimal_identically() -> None:
    expected = 9.99
    assert _adjust_price(10.0, 0.999, 0.0) == pytest.approx(expected, abs=0.005)
    assert _adjust_price(10.0, Decimal("0.999"), Decimal("0")) == pytest.approx(expected, abs=0.005)


def test_adjust_price_uses_half_up_rounding() -> None:
    # 0.005 应按 ROUND_HALF_UP 进位到 0.01
    assert _adjust_price(1.005, 1.0, 0.0) == 1.01
    assert _adjust_price(1.004, 1.0, 0.0) == 1.0


def test_adjust_price_passes_through_none() -> None:
    assert _adjust_price(None, 1.0, 0.0) is None


def test_apply_adjustment_matches_hand_computed_values() -> None:
    bars = [
        _bar(date(2026, 9, 29), close=100.0),
        _bar(date(2026, 9, 30), close=101.0),
    ]
    factors = [
        _factor(date(2026, 9, 29), 0.5, -1.0),
        _factor(date(2026, 9, 30), 1.0, 0.0),
    ]
    result = apply_adjustment(bars, factors, "qfq")
    assert result is not None
    closes = {item.date: item.close for item in result.items}
    assert closes["2026-09-30"] == 101.0
    # 100 * 0.5 - 1 = 49.00
    assert closes["2026-09-29"] == 49.0
    # pre_close 用前一根复权收盘
    assert result.items[1].pre_close == 49.0


def test_apply_adjustment_returns_none_when_factor_missing() -> None:
    bars = [_bar(date(2026, 9, 30), close=101.0)]
    assert apply_adjustment(bars, [_factor(date(2026, 9, 29), 1.0, 0.0)], "qfq") is None


def test_apply_adjustment_rejects_invalid_method() -> None:
    bars = [_bar(date(2026, 9, 30), close=101.0)]
    assert apply_adjustment(bars, [_factor(date(2026, 9, 30), 1.0, 0.0)], "none") is None


def test_apply_adjustment_ten_year_scale_is_consistent() -> None:
    """大区间下逐日换算与逐根独立换算结果一致（Decimal 复用不得引入漂移）。"""
    dates = [date(2016, 10, 10) + _offset(index) for index in range(2427)]
    bars = [_bar(day, close=10.0 + index / 100) for index, day in enumerate(dates)]
    factors = [_factor(day, 0.87, -1.234) for day in dates]

    result = apply_adjustment(bars, factors, "qfq")
    assert result is not None
    for index, item in enumerate(result.items):
        expected = _adjust_price(bars[index].close, 0.87, -1.234)
        assert item.close == expected
