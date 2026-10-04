#!/usr/bin/env python3
"""指数 10 年日 K 导入脚本的关键行为测试（不碰真实数据库与上游）。"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_spec = importlib.util.spec_from_file_location(
    "init_index_daily_from_tdx", ROOT.parent / "scripts/init_index_daily_from_tdx.py"
)
assert _spec and _spec.loader
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _row(day: str, close: float, **extra: object) -> dict:
    numeric = isinstance(close, (int, float))
    row = {
        "datetime": f"{day} 15:00",
        "open": close - 1 if numeric else close,
        "high": close + 2 if numeric else close,
        "low": close - 3 if numeric else close,
        "close": close,
        "volume": 1000.0,
        "amount": 1.0e9,
    }
    row.update(extra)
    return row


class _FakeFrame:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def to_dict(self, _mode: str) -> list[dict]:
        return self._rows


class _FakeQuotes:
    def __init__(self, pages: list[list[dict]]) -> None:
        self.pages = pages
        self.calls: list[int] = []

    def call(self, _kind: str, *, symbol: str, frequency: str, start: int, offset: int):  # noqa: ANN001
        del symbol, frequency
        self.calls.append(start)
        page_index = start // offset
        if page_index >= len(self.pages):
            return _FakeFrame([])
        return _FakeFrame(self.pages[page_index])


class _FakeProvider:
    DAILY_FREQUENCY = "9"

    def __init__(self, quotes: _FakeQuotes) -> None:
        self._quotes = quotes

    @staticmethod
    def _normalize_index_request(symbol: str) -> str:
        return symbol


def _patch_provider(monkeypatch: pytest.MonkeyPatch, quotes: _FakeQuotes) -> None:
    import app.infrastructure.providers.registry as registry

    monkeypatch.setattr(registry, "get_provider", lambda name: _FakeProvider(quotes))


def _full_page(first_day: str, last_day: str) -> list[dict]:
    """构造一个满 800 行的页（TDX 未到数据尾部时每页都是满的）。

    首尾日期精确落在边界上，中间按序号插值，保证整体严格升序。
    """
    start = date.fromisoformat(first_day).toordinal()
    end = date.fromisoformat(last_day).toordinal()
    last_index = script.TDX_PAGE_SIZE - 1
    rows: list[dict] = []
    for index in range(script.TDX_PAGE_SIZE):
        ordinal = (
            start if index == 0 else end if index == last_index else start + round(index * (end - start) / last_index)
        )
        rows.append(_row(date.fromordinal(ordinal).isoformat(), 100 + index))
    return rows


def test_fetch_index_pages_reverses_page_order_but_keeps_rows_ascending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归：TDX 是"start 越大越旧"而页内升序。

    对整个结果做 reverse 会把页内也倒过来，序列变成
    旧→新→更旧→更新，首尾日期完全错位（实测导致只写入 2016-11~2023-06）。
    """
    newest = _full_page("2023-06-15", "2026-09-30")
    older = _full_page("2020-03-02", "2023-06-14")
    quotes = _FakeQuotes([newest, older, []])
    _patch_provider(monkeypatch, quotes)

    rows = script.fetch_index_pages("000001", max_pages=8)

    days = [str(row["datetime"])[:10] for row in rows]
    assert len(days) == 1600
    # 全局升序：最旧在首、最新在尾
    assert days[0] == "2020-03-02"
    assert days[-1] == "2026-09-30"
    assert days == sorted(days), "翻页后整体必须是升序"
    # 满页继续翻，取空停止
    assert quotes.calls == [0, 800, 1600]


def test_derive_pre_close_matches_provider_semantics() -> None:
    """provider 的 _format_index_kline_df 也是用相邻收盘推导，语义必须一致。"""
    records = [
        script._to_bar_record(_row("2026-09-29", 100), "000001", "上证指数", "2026-01-01"),
        script._to_bar_record(_row("2026-09-30", 110), "000001", "上证指数", "2026-01-01"),
        script._to_bar_record(_row("2026-10-09", 99), "000001", "上证指数", "2026-01-01"),
    ]
    script._derive_pre_close(records)

    # 首行没有前值，保持 None
    assert records[0].pre_close is None
    assert records[0].change_pct is None
    assert records[1].pre_close == 100
    assert records[1].change_amount == 10
    assert records[1].change_pct == pytest.approx(10.0)
    assert records[2].pre_close == 110
    assert records[2].change_pct == pytest.approx(-10.0)


def test_to_bar_record_scales_volume_from_lots_to_shares() -> None:
    record = script._to_bar_record(_row("2026-09-30", 100, volume=500.0), "000001", "", "2026-01-01")
    assert record is not None
    # TDX 指数成交量单位是手，入库按股
    assert record.volume == 50000.0
    assert record.market == "cn"
    assert record.instrument_type == "index"
    assert record.adjustment == "none"
    assert record.currency == "CNY"


@pytest.mark.parametrize("close", [0.0, None, -1.0])
def test_to_bar_record_rejects_non_positive_close(close: object) -> None:
    assert script._to_bar_record(_row("2026-09-30", close), "000001", "", "2026-01-01") is None


def test_to_bar_record_respects_start_date() -> None:
    assert script._to_bar_record(_row("2015-12-31", 100), "000001", "", "2016-01-01") is None
    assert script._to_bar_record(_row("2016-01-04", 100), "000001", "", "2016-01-01") is not None


def test_upsert_keeps_existing_rows_from_other_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """skip 语义：非 index-tdx 来源的既有行不能被覆盖。"""
    sql = script._UPSERT_BAR_SQL.format(conflict_clause=script._SKIP_CONFLICT_CLAUSE)
    assert "market_daily_bars.source LIKE 'index-tdx:%'" in sql
    overwrite = script._UPSERT_BAR_SQL.format(conflict_clause=script._OVERWRITE_CONFLICT_CLAUSE)
    assert "LIKE 'index-tdx:%'" not in overwrite


def test_bar_params_binding_count_matches_sql() -> None:
    """回归：少绑一列就会 sqlite3.ProgrammingError。"""
    sql = script._UPSERT_BAR_SQL.format(conflict_clause=script._SKIP_CONFLICT_CLAUSE)
    record = script._to_bar_record(_row("2026-09-30", 100), "000001", "上证指数", "2026-01-01")
    assert record is not None
    assert len(script._bar_params(record, "2026-10-03T00:00:00+00:00")) == sql.count("?")


def test_script_has_no_side_effects_on_import() -> None:
    """导入模块本身不应连库或写库。"""
    assert "sqlite3.connect" not in Path(script.__file__).read_text().split("def main()")[0]
    assert date.today() is not None
    assert sqlite3 is not None
