"""指数日行情 OHLC 归一化：上游精度漂移与实时快照缺字段的区分处理。"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.domain.market import IndexItem, MarketIndices
from app.modules.market_daily.collectors import (
    _normalize_ohlc,
    _widen_ohlc_bounds,
    normalize_indices,
)
from app.modules.market_daily.models import MarketDailyBarRecord

_TRADE_DATE = date(2026, 10, 5)


# ── _normalize_ohlc：日线来源，必须始终产出完整 bar ──


def test_normalize_ohlc_never_invents_a_broken_bar():
    open_price, high, low = _normalize_ohlc(close=10.5, open_price=None, high=None, low=None)
    assert open_price is None
    assert (high, low) == (10.5, 10.5)


def test_normalize_ohlc_widens_bounds_without_touching_close():
    open_price, high, low = _normalize_ohlc(close=10.5, open_price=10.0, high=10.2, low=10.1)
    assert high == 10.5
    assert low == 10.0
    assert open_price == 10.0


def test_normalize_ohlc_drops_non_positive_open():
    assert _normalize_ohlc(close=10.5, open_price=0.0, high=11.0, low=9.0)[0] is None


# ── _widen_ohlc_bounds：实时快照，缺失就保持缺失 ──


def test_widen_ohlc_bounds_keeps_missing_fields_missing():
    """上游没给 high/low 时必须保持 None：填成 close 会谎报「零波动」。"""
    open_price, high, low = _widen_ohlc_bounds(close=10.5, open_price=None, high=None, low=None)
    assert (open_price, high, low) == (None, None, None)


def test_widen_ohlc_bounds_only_widens_out_of_range_values():
    open_price, high, low = _widen_ohlc_bounds(close=10.5, open_price=10.0, high=9.0, low=11.0)
    assert (open_price, high, low) == (10.0, 10.5, 10.0)


def test_widen_ohlc_bounds_leaves_valid_values_untouched():
    assert _widen_ohlc_bounds(close=10.5, open_price=10.0, high=12.0, low=9.5) == (10.0, 12.0, 9.5)


def test_widen_ohlc_bounds_drops_non_positive_open():
    assert _widen_ohlc_bounds(close=10.5, open_price=-1.0, high=12.0, low=9.5)[0] is None


def test_widen_ohlc_bounds_handles_half_present_fields():
    open_price, high, low = _widen_ohlc_bounds(close=10.5, open_price=10.0, high=None, low=11.0)
    assert high is None
    assert low == 10.0


# ── normalize_indices：端到端确认不编造、不崩溃 ──


def _build(indices: list[IndexItem]) -> list[MarketDailyBarRecord]:
    return normalize_indices(
        MarketIndices(indices=indices, source="test"),
        market="cn",
        trade_date=_TRADE_DATE,
    )


def test_normalize_indices_absorbs_precision_drift():
    records = _build([IndexItem(code="HSCEI", name="国企指数", price=8051.67041, open=8021.07, high=8051.67, low=7980.11)])
    assert len(records) == 1
    record = records[0]
    assert record.close == pytest.approx(8051.67041)
    assert record.high == pytest.approx(8051.67041)
    assert record.low == pytest.approx(7980.11)


def test_normalize_indices_keeps_absent_high_low_absent():
    records = _build([IndexItem(code="000001", name="上证指数", price=3000.0, open=2990.0)])
    assert len(records) == 1
    record = records[0]
    assert record.high is None
    assert record.low is None
    assert record.open == 2990.0
    assert record.close == 3000.0


def test_normalize_indices_skips_items_without_price():
    assert _build([IndexItem(code="000001", name="上证指数", price=None)]) == []
    assert _build([IndexItem(code="000001", name="上证指数", price=0.0)]) == []


# ── fetch_cn_indices：这条是真正在跑的 cn_index 分区 ──


_CN_INDEX_SYMBOLS = ("000001", "399001", "399006", "000688", "000300", "000905", "000852")


def test_cn_index_record_model_rejects_raw_precision_drift():
    with pytest.raises(ValueError, match="high 不能低于 close/open"):
        MarketDailyBarRecord(
            market="cn",
            instrument_type="index",
            code="000300",
            name="沪深300",
            trade_date=_TRADE_DATE,
            currency="CNY",
            open=3900.10,
            high=3950.22,
            low=3880.00,
            close=3950.22021,
            source="index_kline",
        )


@pytest.mark.asyncio
async def test_fetch_cn_indices_absorbs_precision_drift(monkeypatch):
    """cn_index 分区此前直接透传 high/low，同样会被精度漂移打崩。"""
    from app.domain.market import KlineData, KlineItem
    from app.financial_data.market.quotes import index_kline as index_kline_module
    from app.modules.market_daily import collectors as collectors_module
    from app.modules.market_daily.collectors import fetch_cn_indices

    # 交易日哨兵会打真实上游，与本用例要验证的 OHLC 归一化无关
    monkeypatch.setattr(collectors_module, "_verify_cn_trade_date", AsyncMock())

    target = _TRADE_DATE.isoformat()

    async def fake_load(symbol: str, period: str, start: str, end: str) -> KlineData:
        close = 3950.22021 if symbol == "000300" else 3000.0
        high = 3950.22 if symbol == "000300" else 3100.0
        return KlineData(
            code=symbol,
            period="daily",
            adjust="",
            items=[KlineItem(
                code=symbol, date=target,
                open=close - 10, close=close, high=high, low=close - 20,
                volume=1.0, amount=1.0,
            )],
            source="test",
        )

    monkeypatch.setattr(index_kline_module, "_load_index_kline", fake_load)

    result = await fetch_cn_indices(_TRADE_DATE)
    assert len(result.records) == len(_CN_INDEX_SYMBOLS)
    drifted = next(item for item in result.records if item.code == "000300")
    assert drifted.close == pytest.approx(3950.22021)
    assert drifted.high == pytest.approx(3950.22021)
    assert drifted.high >= max(drifted.close, drifted.open or drifted.close)


@pytest.mark.asyncio
async def test_fetch_cn_indices_leaves_clean_rows_untouched(monkeypatch):
    from app.domain.market import KlineData, KlineItem
    from app.financial_data.market.quotes import index_kline as index_kline_module
    from app.modules.market_daily import collectors as collectors_module
    from app.modules.market_daily.collectors import fetch_cn_indices

    # 交易日哨兵会打真实上游，与本用例要验证的 OHLC 归一化无关
    monkeypatch.setattr(collectors_module, "_verify_cn_trade_date", AsyncMock())

    target = _TRADE_DATE.isoformat()

    async def fake_load(symbol: str, period: str, start: str, end: str) -> KlineData:
        return KlineData(
            code=symbol, period="daily", adjust="",
            items=[KlineItem(
                code=symbol, date=target,
                open=2990.0, close=3000.0, high=3100.0, low=2880.0,
                volume=1.0, amount=1.0,
            )],
            source="test",
        )

    monkeypatch.setattr(index_kline_module, "_load_index_kline", fake_load)

    result = await fetch_cn_indices(_TRADE_DATE)
    sample = next(item for item in result.records if item.code == "000001")
    assert (sample.open, sample.high, sample.low, sample.close) == (2990.0, 3100.0, 2880.0, 3000.0)


@pytest.mark.asyncio
async def test_fetch_cn_indices_still_requires_all_symbols(monkeypatch):
    """归一化不能掩盖「指数缺失」：缺一个就必须整体失败。"""
    from app.domain.market import KlineData, KlineItem
    from app.financial_data.market.quotes import index_kline as index_kline_module
    from app.modules.market_daily import collectors as collectors_module
    from app.modules.market_daily.collectors import fetch_cn_indices

    # 交易日哨兵会打真实上游，与本用例要验证的 OHLC 归一化无关
    monkeypatch.setattr(collectors_module, "_verify_cn_trade_date", AsyncMock())

    target = _TRADE_DATE.isoformat()

    async def fake_load(symbol: str, period: str, start: str, end: str) -> KlineData:
        if symbol == "000852":
            return KlineData(code=symbol, period="daily", adjust="", items=[], source="test")
        return KlineData(
            code=symbol, period="daily", adjust="",
            items=[KlineItem(
                code=symbol, date=target,
                open=2990.0, close=3000.0, high=3100.0, low=2880.0,
                volume=1.0, amount=1.0,
            )],
            source="test",
        )

    monkeypatch.setattr(index_kline_module, "_load_index_kline", fake_load)

    with pytest.raises(RuntimeError, match="A 股指数当日日线不完整"):
        await fetch_cn_indices(_TRADE_DATE)
