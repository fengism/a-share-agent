"""港股指数日线采集：新浪 float32 还原值导致的 OHLC 越界回归。"""

from __future__ import annotations

import asyncio
from datetime import date

import pandas as pd
import pytest

from app.modules.market_daily.collectors import fetch_hk_indices
from app.modules.market_daily.models import MarketDailyBarRecord

_TRADE_DATE = date(2026, 10, 5)


class _StubHKService:
    """按 symbol 返回固定日线，模拟新浪港股指数日线接口。"""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames
        self.provider = self
        self.requested: list[str] = []

    async def _call(self, operation: str, function, *args):
        assert operation == "fetch_hk_index_daily"
        symbol = args[0]
        self.requested.append(symbol)
        return self._frames.get(symbol, pd.DataFrame())

    def fetch_hk_index_daily(self, symbol: str) -> pd.DataFrame:  # pragma: no cover - 由 _call 代理
        raise AssertionError("不应直接调用 provider")


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows).rename(columns={
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount",
    })


def _three_index_frames(hscei_row: dict) -> dict[str, pd.DataFrame]:
    """三个指数都返回同一批行，仅 HSCEI 使用传入的异常行。"""
    normal = {
        "日期": "2026-10-05",
        "开盘": 23963.41, "最高": 24040.34, "最低": 23835.68,
        "收盘": 24040.33984, "成交量": 6178964738, "成交额": 98101632853,
    }
    return {
        "HSI": _frame([normal]),
        "HSTECH": _frame([normal]),
        "HSCEI": _frame([hscei_row]),
    }


def test_record_model_rejects_the_raw_upstream_values():
    """先确认模型确实会拒绝原始值：否则下面的修复就成了 placebo。"""
    with pytest.raises(ValueError, match="high 不能低于 close/open"):
        MarketDailyBarRecord(
            market="hk",
            instrument_type="index",
            code="HSCEI",
            name="HSCEI",
            trade_date=_TRADE_DATE,
            currency="HKD",
            open=8021.07,
            high=8051.67,
            low=7980.11,
            close=8051.67041,
            source="sina_hk.index_daily",
        )


def test_collect_hk_indices_absorbs_float32_close_drift():
    """指数收在当日最高点时，float32 还原的 close 会略微越过 high。"""
    frames = _three_index_frames({
        "日期": "2026-10-05",
        "开盘": 8021.07, "最高": 8051.67, "最低": 7980.11,
        "收盘": 8051.67041, "成交量": 785108113, "成交额": 24859395854,
    })
    result = asyncio.run(fetch_hk_indices(_TRADE_DATE, service=_StubHKService(frames)))

    assert result.segment == "hk_index"
    assert len(result.records) == 3
    hscei = next(item for item in result.records if item.code == "HSCEI")
    # 收盘价是真实价格，必须原样保留；只放宽 high 去包住它
    assert hscei.close == pytest.approx(8051.67041)
    assert hscei.high == pytest.approx(8051.67041)
    assert hscei.high >= max(hscei.close, hscei.open)
    assert hscei.low == pytest.approx(7980.11)


def test_collect_hk_indices_absorbs_float32_low_drift():
    """指数收在当日最低点时同理：float32 还原会略微跌破 low。"""
    frames = _three_index_frames({
        "日期": "2026-10-05",
        "开盘": 9198.60, "最高": 9219.02, "最低": 9083.53,
        "收盘": 9083.5293, "成交量": 3139476374, "成交额": 91365618995,
    })
    result = asyncio.run(fetch_hk_indices(_TRADE_DATE, service=_StubHKService(frames)))

    hscei = next(item for item in result.records if item.code == "HSCEI")
    assert hscei.close == pytest.approx(9083.5293)
    assert hscei.low == pytest.approx(9083.5293)
    assert hscei.low <= min(hscei.close, hscei.open)


def test_collect_hk_indices_leaves_clean_rows_untouched():
    """数据本来就合法时不得被改动，避免用归一化掩盖真实上游问题。"""
    frames = _three_index_frames({
        "日期": "2026-10-05",
        "开盘": 8021.07, "最高": 8100.00, "最低": 7980.11,
        "收盘": 8051.67, "成交量": 785108113, "成交额": 24859395854,
    })
    result = asyncio.run(fetch_hk_indices(_TRADE_DATE, service=_StubHKService(frames)))

    hscei = next(item for item in result.records if item.code == "HSCEI")
    assert (hscei.open, hscei.high, hscei.low, hscei.close) == (8021.07, 8100.0, 7980.11, 8051.67)


def test_collect_hk_indices_still_requires_all_three_indices():
    """归一化不能掩盖「指数缺失」：仍然必须凑齐 3 个指数。"""
    frames = _three_index_frames({
        "日期": "2026-10-05",
        "开盘": 8021.07, "最高": 8051.67, "最低": 7980.11,
        "收盘": 8051.67041, "成交量": 785108113, "成交额": 24859395854,
    })
    del frames["HSTECH"]
    with pytest.raises(RuntimeError, match="港股指数当日市场日行情不完整"):
        asyncio.run(fetch_hk_indices(_TRADE_DATE, service=_StubHKService(frames)))
