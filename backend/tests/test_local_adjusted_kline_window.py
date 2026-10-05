"""本地复权 K 线按区间读取的行为测试。

背景：此前每次都从 ``date.min`` 全量读取历史 bar 再裁剪，长牛股代价随历史长度增长。
这里锁定"只读区间 + 锚点窗口"后仍保持首根前收衔接、区间外不返回，以及区间内无
真实 bar 时回退（返回 None）的行为。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

import app.modules.market_daily.adjustment as adjustment
from app.modules.market_daily.models import MarketDailyAdjustmentFactor, MarketDailyBar

ANCHOR_LOOKBACK = adjustment._ADJUSTMENT_ANCHOR_LOOKBACK_DAYS


def _bar(trade_date: date, close: float) -> MarketDailyBar:
    now = datetime.now(UTC)
    return MarketDailyBar(
        market="cn",
        instrument_type="stock",
        code="600519",
        trade_date=trade_date,
        currency="CNY",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        amount=1000.0,
        source="test",
        verification_status="confirmed",
        revision=1,
        first_refreshed_at=now,
        last_refreshed_at=now,
    )


def _factor(trade_date: date) -> MarketDailyAdjustmentFactor:
    # 恒等复权，便于直接比对原始 close
    return MarketDailyAdjustmentFactor(
        code="600519",
        trade_date=trade_date,
        qfq_multiplier=1.0,
        qfq_offset=0.0,
        hfq_multiplier=1.0,
        hfq_offset=0.0,
        action_hash="hash",
        algorithm_version="test",
        calculated_at=datetime.now(UTC),
    )


class _FakeRepository:
    def __init__(self, bars: list[MarketDailyBar]) -> None:
        self._bars = bars
        self.read_start: date | None = None
        self.read_end: date | None = None

    def initialize(self) -> None:
        return None

    def list_bars(self, *, market, instrument_type, code, start_date, end_date):
        self.read_start = start_date
        self.read_end = end_date
        return [bar for bar in self._bars if start_date <= bar.trade_date <= end_date]

    def list_adjustment_factors(self, code, start_date, end_date, market="cn"):
        return [_factor(bar.trade_date) for bar in self._bars if start_date <= bar.trade_date <= end_date]


async def _factors_available(code: str, *, force: bool = False) -> bool:
    return True


@pytest.mark.asyncio
async def test_reads_only_requested_window_with_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = [date(2026, 9, 1) + timedelta(days=index) for index in range(40)]
    bars = [_bar(day, close=10.0 + index) for index, day in enumerate(dates)]
    fake = _FakeRepository(bars)
    monkeypatch.setattr(adjustment, "_repository", fake)
    monkeypatch.setattr(adjustment, "ensure_adjustment_factors", _factors_available)

    start_date = dates[20]
    end_date = dates[30]
    result = await adjustment.load_local_adjusted_daily_kline("600519", start_date, end_date, "qfq")

    assert result is not None
    # 只读到区间 + 锚点窗口，而不是 date.min 全量
    assert fake.read_start == start_date - timedelta(days=ANCHOR_LOOKBACK)
    assert fake.read_end == end_date
    # 只返回区间内 bar
    assert [item.date for item in result.items] == [day.isoformat() for day in dates[20:31]]
    # 首根前收来自锚点窗口中的前一根（dates[19]，close=29.0）
    assert result.items[0].pre_close == bars[19].close


@pytest.mark.asyncio
async def test_returns_none_when_range_has_no_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = [date(2026, 9, 1) + timedelta(days=index) for index in range(10)]
    bars = [_bar(day, close=10.0 + index) for index, day in enumerate(dates)]
    fake = _FakeRepository(bars)
    monkeypatch.setattr(adjustment, "_repository", fake)
    monkeypatch.setattr(adjustment, "ensure_adjustment_factors", _factors_available)

    # 区间远在全部 bar 之后，区间内无真实 bar，应回退上游
    start_date = dates[-1] + timedelta(days=100)
    end_date = start_date + timedelta(days=5)
    result = await adjustment.load_local_adjusted_daily_kline("600519", start_date, end_date, "qfq")

    assert result is None
