"""每日复盘采集口径元数据：数据归属日、宏观事件时点裁剪与北向资金降级。"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.market import market_today
from app.financial_data.market.macro.schemas import MacroAnalysisEvent, MacroAnalysisResponse
from app.financial_data.market.public import NorthboundHistoryPoint, NorthboundHistoryResponse
from app.modules.daily_review import collector


class _StubIndices:
    date = "2026-10-15"
    source = "stub"
    indices: list = []


async def _zero(*args: object, **kwargs: object) -> list:
    return []


def _macro_response(*dates: str, pending: bool = False) -> MacroAnalysisResponse:
    return MacroAnalysisResponse(
        period="2026-09 ~ 2026-10",
        summary="综述",
        events=[
            MacroAnalysisEvent(date=value, category="物价", title=f"事件{value}", pending=pending)
            for value in dates
        ],
        policy_signals=[],
    )


def _patch_sources(
    monkeypatch: pytest.MonkeyPatch,
    *,
    macro_analysis: MacroAnalysisResponse | None = None,
    northbound: object | None = None,
    break_pool: object | None = None,
) -> None:
    async def _indices() -> _StubIndices:
        return _StubIndices()

    async def _macro() -> MacroAnalysisResponse:
        return macro_analysis or _macro_response()

    async def _northbound(target_date: date) -> object:
        return northbound if northbound is not None else []

    async def _break(target_date: date) -> object:
        return break_pool if break_pool is not None else []

    monkeypatch.setattr(collector, "get_indices", _indices)
    monkeypatch.setattr(collector, "get_hot_stocks", _zero)
    monkeypatch.setattr(collector, "get_ths_hot_concept", _zero)
    monkeypatch.setattr(collector, "get_ths_hot_industry", _zero)
    monkeypatch.setattr(collector, "get_dragon_tiger_list", _zero)
    monkeypatch.setattr(collector, "get_market_statistics", _zero)
    monkeypatch.setattr(collector, "get_market_news", _zero)
    monkeypatch.setattr(collector, "get_market_volume_stats", _zero)
    monkeypatch.setattr(collector, "get_macro_data", _zero)
    monkeypatch.setattr(collector, "get_macro_analysis", _macro)
    monkeypatch.setattr(collector, "get_limit_up_ladder", _zero)
    monkeypatch.setattr(collector, "get_limit_break_pool", _break)
    monkeypatch.setattr(collector, "_target_northbound", _northbound)
    monkeypatch.setattr(collector, "search_financial_policy_news", _zero)


def test_data_date_marks_dateless_rankings_with_fetch_date() -> None:
    """热门榜快照没有日期，历史复盘必须暴露这是「当前快照」而不是复盘日数据。"""
    rankings = [{"name": "贵州茅台", "change_pct": 3.1}]

    assert (
        collector._data_date(rankings, "2026-10-01", is_realtime=False)
        == market_today().isoformat()
    )


def test_data_date_prefers_explicit_item_date() -> None:
    items = [{"trade_date": "2026-10-13T15:00:00", "name": "x"}]

    assert collector._data_date(items, "2026-10-01", is_realtime=False) == "2026-10-13"


def test_data_date_uses_macro_period_for_dict() -> None:
    macro = {"cpi": {"latest": {"TIME": "2026-09-30", "NATIONAL_SAME": "0.9"}}}

    assert collector._data_date(macro, "2026-10-01", is_realtime=False) == "2026-09-30"


def test_macro_period_picks_latest_available() -> None:
    macro = {
        "cpi": {"latest": {"TIME": "2026-08-31"}},
        "pmi": {"latest": {"TIME": "2026-09-30"}},
        "m2": {"latest": {"TIME": "2026-07-31"}},
    }

    assert collector._macro_period(macro) == "2026-09-30"


def test_clip_macro_analysis_drops_events_after_review_date() -> None:
    response = _macro_response("2026-10-13", "2026-10-14", "2026-10-16", pending=True)

    clipped = collector._clip_macro_analysis(response, "2026-10-14")

    assert [event.date for event in clipped.events] == ["2026-10-13", "2026-10-14"]
    assert clipped.pending_count == 2
    # 共享缓存对象不能被就地改写
    assert len(response.events) == 3


def test_clip_macro_analysis_returns_same_object_when_nothing_to_clip() -> None:
    response = _macro_response("2026-10-13", "2026-10-14")

    assert collector._clip_macro_analysis(response, "2026-10-14") is response
    assert collector._clip_macro_analysis(None, "2026-10-14") is None


async def test_target_northbound_falls_back_to_latest_trading_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = NorthboundHistoryResponse(
        updated_at="2026-10-15T16:00:00",
        items=[
            NorthboundHistoryPoint(date="2026-10-13", north_money=12.5),
            NorthboundHistoryPoint(date="2026-10-12", north_money=-3.0),
        ],
    )

    async def _history(limit: int) -> NorthboundHistoryResponse:
        return response

    monkeypatch.setattr(collector, "get_northbound_history", _history)

    point, note = await collector._target_northbound(date(2026, 10, 15))

    assert point.date == "2026-10-13"
    assert "2026-10-13" in note


async def test_target_northbound_raises_without_any_earlier_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = NorthboundHistoryResponse(
        updated_at="2026-10-15T16:00:00",
        items=[NorthboundHistoryPoint(date="2026-10-16", north_money=1.0)],
    )

    async def _history(limit: int) -> NorthboundHistoryResponse:
        return response

    monkeypatch.setattr(collector, "get_northbound_history", _history)

    with pytest.raises(collector.HistoricalReviewDataUnavailableError):
        await collector._target_northbound(date(2026, 10, 15))


async def test_collect_marks_northbound_partial_and_unwraps_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    point = NorthboundHistoryPoint(date="2026-10-13", north_money=12.5)
    _patch_sources(monkeypatch, northbound=(point, "复盘日 2026-10-15 未披露北向资金，已回退最近交易日 2026-10-13"))

    collection = await collector.collect_daily_review_data(date(2026, 10, 15), use_realtime=False)

    assert collection.values["northbound_funds"] is point
    status = collection.source_status["northbound_funds"]
    assert status.status == "partial"
    assert status.data_date == "2026-10-13"
    assert "已回退最近交易日" in status.error


async def test_collect_clips_future_macro_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _macro_response("2026-10-14", "2026-10-16")
    _patch_sources(monkeypatch, macro_analysis=response)

    collection = await collector.collect_daily_review_data(date(2026, 10, 15), use_realtime=False)

    macro = collection.values["macro_analysis"]
    assert [event.date for event in macro.events] == ["2026-10-14"]


async def test_collect_includes_limit_break_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = {"date": "2026-10-15", "total": 1, "items": [{"code": "000001", "name": "甲", "open_times": 2}]}
    _patch_sources(monkeypatch, break_pool=pool)

    collection = await collector.collect_daily_review_data(date(2026, 10, 15), use_realtime=False)

    assert collection.values["limit_break_pool"] == pool
    assert collection.source_status["limit_break_pool"].status == "complete"
