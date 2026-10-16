"""每日复盘接入 AI 宏观事件解读：快照存储 + Prompt 格式化。"""

from __future__ import annotations

from datetime import date

import pytest

from app.financial_data.market.macro.schemas import MacroAnalysisResponse
from app.modules.daily_review import collector, review_builder
from app.modules.daily_review.models import DailyReviewDataSnapshot
from app.modules.daily_review.prompts import MARKET_USER_PROMPT

_MACRO_ANALYSIS = {
    "period": "2026-09-14 ~ 2026-10-15",
    "summary": "综述内容",
    "sentiment": "偏多",
    "pending_count": 1,
    "policy_signals": ["稳增长"],
    "events": [
        {
            "date": "2026-10-14",
            "category": "物价",
            "title": "CPI上涨",
            "interpretation": "利好消费板块",
            "impact": "偏多",
            "pending": False,
        },
        {
            "date": "2026-10-15",
            "category": "其他",
            "title": "新发布数据",
            "interpretation": "新发布数据",
            "impact": "中性",
            "pending": True,
        },
    ],
}


def test_macro_event_summary_marks_pending_events() -> None:
    snapshot = DailyReviewDataSnapshot(macro_analysis=_MACRO_ANALYSIS)

    text = review_builder._macro_event_summary(snapshot)

    assert "AI 宏观综述（偏多）：综述内容" in text
    assert "1 条最新事件仍在后台解读" in text
    assert "- [2026-10-14]（物价/偏多）CPI上涨 — 利好消费板块" in text
    assert "- [2026-10-15] 新发布数据（待解读）" in text
    assert "政策信号：稳增长" in text


def test_macro_summary_appends_ai_events() -> None:
    snapshot = DailyReviewDataSnapshot(
        macro_data={"cpi": {"latest": {"TIME": "2026-09", "NATIONAL_SAME": "0.9"}}},
        macro_analysis=_MACRO_ANALYSIS,
    )

    text = review_builder._macro_summary(snapshot)

    assert "CPI(2026-09)" in text
    assert "AI 宏观综述（偏多）：综述内容" in text


def test_macro_summary_without_analysis_stays_unchanged() -> None:
    snapshot = DailyReviewDataSnapshot(macro_data={})

    assert review_builder._macro_summary(snapshot) == "暂无最新宏观数据"


def test_build_snapshot_keeps_macro_analysis() -> None:
    response = MacroAnalysisResponse(period="p", summary="s", events=[], policy_signals=[])

    snapshot = review_builder.build_snapshot(
        None, None, None, None, None, None, None, None, None, macro_analysis=response
    )

    assert snapshot.macro_analysis["summary"] == "s"
    assert snapshot.macro_analysis["pending_count"] == 0


def test_build_prompt_includes_ai_macro_events() -> None:
    snapshot = DailyReviewDataSnapshot(macro_analysis=_MACRO_ANALYSIS)

    prompt = review_builder.build_prompt("2026-10-15", snapshot, MARKET_USER_PROMPT)

    assert "# 宏观经济数据（含 AI 事件解读" in prompt
    assert "AI 宏观综述（偏多）：综述内容" in prompt
    assert "新发布数据（待解读）" in prompt


class _Stub:
    date = "2026-10-15"
    source = "stub"
    indices: list = []


async def test_collect_marks_macro_analysis_partial_when_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _zero(*args, **kwargs):  # noqa: ANN002, ANN003
        return []

    pending = MacroAnalysisResponse(
        period="p",
        summary="",
        events=[],
        policy_signals=[],
        pending_count=2,
    )

    async def _macro() -> MacroAnalysisResponse:
        return pending

    async def _indices() -> _Stub:
        return _Stub()

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
    monkeypatch.setattr(collector, "_target_northbound", _zero)
    monkeypatch.setattr(collector, "search_financial_policy_news", _zero)

    collection = await collector.collect_daily_review_data(date(2026, 10, 15), use_realtime=True)

    status = collection.source_status["macro_analysis"]
    assert status.status == "partial"
    assert "2 条宏观事件待后台解读" in status.error
    assert collection.values["macro_analysis"] is pending
