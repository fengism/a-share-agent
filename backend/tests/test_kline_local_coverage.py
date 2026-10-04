"""K 线本地覆盖与上游补采窗口的判定测试。

背景：本地库已覆盖近 10 年日线，整段回源既慢又会拖垮冷启动；
这里锁定"本地覆盖则不打上游、只补含交易日的缺口"的行为。
"""

from __future__ import annotations

from datetime import date

from app.domain.market import KlineData, KlineItem
from app.financial_data.stock.quotes.kline import (
    _has_cn_trading_day,
    _merge_upstream_parts,
    _upstream_windows,
)


def _item(day: str) -> KlineItem:
    return KlineItem(
        code="600519",
        date=day,
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        pre_close=10.0,
        volume=1000,
        amount=10000,
    )


def _local(days: list[str]) -> KlineData:
    return KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="market_daily:confirmed",
        items=[_item(day) for day in days],
    )


def test_fully_covered_range_needs_no_upstream() -> None:
    local = _local(["2026-09-28", "2026-09-29", "2026-09-30"])
    assert _upstream_windows(local, date(2026, 9, 28), date(2026, 9, 30)) is None


def test_tail_with_trading_day_is_fetched_incrementally() -> None:
    local = _local(["2026-09-28", "2026-09-29", "2026-09-30"])
    # 2026-10-01~10-07 为休市，10-08 起恢复交易
    windows = _upstream_windows(local, date(2026, 9, 28), date(2026, 10, 9))
    assert windows == [(date(2026, 10, 8), date(2026, 10, 9))]


def test_tail_of_holidays_only_needs_no_upstream() -> None:
    local = _local(["2026-09-29", "2026-09-30"])
    # 国庆长假 + 周末，区间内无交易日
    assert _upstream_windows(local, date(2026, 9, 29), date(2026, 10, 7)) is None


def test_head_gap_with_trading_day_is_fetched() -> None:
    local = _local(["2026-09-30"])
    windows = _upstream_windows(local, date(2026, 9, 21), date(2026, 9, 30))
    assert windows == [(date(2026, 9, 21), date(2026, 9, 29))]


def test_head_gap_of_holidays_is_ignored() -> None:
    local = _local(["2026-09-30"])
    # 起点到本地首根之间只有休市日，不应回源
    assert _upstream_windows(local, date(2026, 10, 1), date(2026, 10, 9)) == [(date(2026, 10, 8), date(2026, 10, 9))]


def test_both_head_and_tail_gaps_produce_two_windows() -> None:
    local = _local(["2026-09-30"])
    windows = _upstream_windows(local, date(2026, 9, 21), date(2026, 10, 9))
    assert windows == [
        (date(2026, 9, 21), date(2026, 9, 29)),
        (date(2026, 10, 8), date(2026, 10, 9)),
    ]


def test_missing_local_data_falls_back_to_full_range() -> None:
    assert _upstream_windows(None, date(2026, 9, 21), date(2026, 10, 9)) == []
    assert _upstream_windows(_local([]), date(2026, 9, 21), date(2026, 10, 9)) == []


def test_has_cn_trading_day_boundaries() -> None:
    assert _has_cn_trading_day(date(2026, 9, 28), date(2026, 9, 30)) is True
    assert _has_cn_trading_day(date(2026, 10, 1), date(2026, 10, 7)) is False
    assert _has_cn_trading_day(date(2026, 10, 7), date(2026, 10, 1)) is False


def test_merge_upstream_parts_dedupes_and_sorts() -> None:
    head = KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="head",
        items=[_item("2026-09-21"), _item("2026-09-22")],
    )
    tail = KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="tail",
        items=[_item("2026-10-08")],
    )
    assert _merge_upstream_parts([head]) is head

    merged = _merge_upstream_parts([head, tail])
    assert [item.date for item in merged.items] == ["2026-09-21", "2026-09-22", "2026-10-08"]


def test_merge_upstream_parts_prefers_later_window_on_conflict() -> None:
    older = KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="older",
        items=[
            KlineItem(
                code="600519",
                date="2026-09-30",
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                pre_close=1.0,
                volume=1,
                amount=1,
            )
        ],
    )
    newer = KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="newer",
        items=[
            KlineItem(
                code="600519",
                date="2026-09-30",
                open=2.0,
                high=2.0,
                low=2.0,
                close=2.0,
                pre_close=1.0,
                volume=2,
                amount=2,
            )
        ],
    )
    merged = _merge_upstream_parts([older, newer])
    assert len(merged.items) == 1
    assert merged.items[0].close == 2.0
