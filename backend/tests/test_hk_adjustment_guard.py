"""港股因子读取的防护：hfq 为 NULL 时必须回退，不能给近似值。"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.market_daily.adjustment import apply_adjustment  # noqa: E402
from app.modules.market_daily.models import (  # noqa: E402
    MarketDailyAdjustmentFactor,
    MarketDailyBar,
)


def _bar(day: date, close: float = 100.0) -> MarketDailyBar:
    return MarketDailyBar(
        market="hk",
        instrument_type="stock",
        code="00001",
        name="长和",
        trade_date=day,
        currency="HKD",
        open=close - 1,
        high=close + 2,
        low=close - 3,
        close=close,
        pre_close=close - 1,
        change_amount=1.0,
        change_pct=1.0,
        volume=1000.0,
        amount=1.0e6,
        adjustment="none",
        source="hk-csv:raw",
        verification_status="confirmed",
        revision=1,
        first_refreshed_at=datetime.now(UTC),
        last_refreshed_at=datetime.now(UTC),
        data_hash="x",
        content_hash="x",
        provenance_hash="x",
    )


def _factor(
    day: date,
    *,
    qfq_mul: float = 1.0,
    qfq_add: float = -26.825,
    hfq_mul: float | None = None,
    hfq_add: float | None = None,
) -> MarketDailyAdjustmentFactor:
    return MarketDailyAdjustmentFactor(
        market="hk",
        code="00001",
        trade_date=day,
        qfq_multiplier=qfq_mul,
        qfq_offset=qfq_add,
        hfq_multiplier=hfq_mul,
        hfq_offset=hfq_add,
        action_hash="x",
        algorithm_version="hk-csv-qfq-affine-v1",
        source="hk-csv:factors",
        calculated_at=datetime.now(UTC),
    )


def test_qfq_works_with_null_hfq_factors() -> None:
    bars = [_bar(date(2026, 5, 26), 70.55), _bar(date(2026, 5, 27), 67.5)]
    factors = [
        _factor(date(2026, 5, 26), qfq_add=-2.347),
        _factor(date(2026, 5, 27), qfq_add=-0.745),
    ]

    result = apply_adjustment(bars, factors, "qfq")

    assert result is not None
    assert result.adjustment_verified is True
    # 前复权 = 原始价 + offset（跨除息日应连续，无 -1.6 假跳变）
    assert result.items[0].close == pytest.approx(68.203)
    assert result.items[1].close == pytest.approx(66.755)


def test_hfq_returns_none_when_factors_have_null_hfq() -> None:
    """回归：HK 因子 hfq 为 NULL 时，hfq 请求必须回退上游，不能拿 qfq 因子凑数。"""
    bars = [_bar(date(2026, 5, 26), 70.55)]
    factors = [_factor(date(2026, 5, 26), hfq_mul=None, hfq_add=None)]

    assert apply_adjustment(bars, factors, "hfq") is None


def test_hfq_still_works_when_factors_are_complete() -> None:
    bars = [_bar(date(2026, 5, 26), 70.55), _bar(date(2026, 5, 27), 67.5)]
    factors = [
        _factor(date(2026, 5, 26), hfq_mul=1.0, hfq_add=24.478),
        _factor(date(2026, 5, 27), hfq_mul=1.0, hfq_add=26.08),
    ]

    result = apply_adjustment(bars, factors, "hfq")

    assert result is not None
    assert result.items[0].close == pytest.approx(95.028)
    assert result.items[1].close == pytest.approx(93.58)
