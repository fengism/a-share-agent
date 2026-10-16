"""复盘闭环（自检）与情绪周期趋势：确定性聚合、落库与 Prompt 接线。

这些能力都不依赖 LLM：摘要来自快照算术与复盘结论，自检来自本地日线（缺失才降级），
趋势是纯函数聚合，因此可以用固定样本逐条断言。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.modules.daily_review import cycle_store, cycle_trend, review_builder, self_check
from app.modules.daily_review.models import (
    DailyReviewCycleRecord,
    DailyReviewDataSnapshot,
    DailyReviewIndexCheck,
    DailyReviewIndexMove,
    DailyReviewPreviousCheck,
    DailyReviewSentimentCycle,
    DailyReviewWatchCheck,
    DailyReviewWatchItem,
)
from app.modules.daily_review.prompts import MARKET_USER_PROMPT


def _snapshot(
    *,
    indices: list | None = None,
    market_statistics: dict | None = None,
    limit_up_ladder: dict | None = None,
    limit_break_pool: dict | None = None,
) -> DailyReviewDataSnapshot:
    return DailyReviewDataSnapshot(
        requested_date="2026-10-15",
        effective_date="2026-10-15",
        indices=indices or [],
        market_statistics=market_statistics or {},
        limit_up_ladder=limit_up_ladder or {},
        limit_break_pool=limit_break_pool or {},
    )


def _record(
    date_text: str,
    *,
    stage: str = "修复回暖",
    index_change_pct: float = 1.0,
    limit_up_count: int | None = 60,
    watchlist: list[DailyReviewWatchItem] | None = None,
) -> DailyReviewCycleRecord:
    return DailyReviewCycleRecord(
        date=date_text,
        stage=stage,
        indices=[DailyReviewIndexMove(code="000001", name="上证指数", change_pct=index_change_pct)],
        limit_up_count=limit_up_count,
        watchlist=watchlist or [],
    )


def _clear_records() -> None:
    with unit_of_work() as work:
        work.connection.execute("DELETE FROM daily_review_cycle_records")


@pytest.fixture(autouse=True)
def _clean_cycle_records():
    _clear_records()
    yield
    _clear_records()


# --- cycle_store（按日摘要落库） -------------------------------------------------


def test_save_and_load_cycle_record_roundtrip():
    snapshot = _snapshot(
        indices=[{"code": "000001", "name": "上证指数", "change_pct": 0.8}],
        market_statistics={"up_count": 3000, "down_count": 2000, "limit_up_count": 71, "limit_down_count": 9},
        limit_up_ladder={"stocks": [{"name": "甲"}, {"name": "乙"}]},
        limit_break_pool={"items": [{"name": "丙"}, {"name": "丁"}]},
    )
    record = cycle_store.build_cycle_record(
        date_text="2026-10-15",
        snapshot=snapshot,
        sentiment_cycle=DailyReviewSentimentCycle(stage="主升共振", ladder_health="梯队健康"),
        watchlist=[DailyReviewWatchItem(name="甲", code="000001", role="连板最高板")],
        key_levels=["上证 3250 支撑", "  "],
    )

    cycle_store.save_cycle_record(record)
    loaded = cycle_store.load_cycle_record("2026-10-15")

    assert loaded is not None
    assert loaded.stage == "主升共振"
    assert loaded.limit_up_count == 71
    assert loaded.up_down_ratio == pytest.approx(1.5)
    # 炸板 2 家 /（涨停 2 家 + 炸板 2 家）
    assert loaded.break_rate == pytest.approx(0.5)
    assert [item.name for item in loaded.watchlist] == ["甲"]
    assert loaded.key_levels == ["上证 3250 支撑"]
    assert cycle_store.load_cycle_record("2026-10-14") is None


def test_previous_cycle_record_uses_strictly_earlier_date():
    cycle_store.save_cycle_record(_record("2026-10-13"))
    cycle_store.save_cycle_record(_record("2026-10-14"))
    cycle_store.save_cycle_record(_record("2026-10-15"))

    assert cycle_store.previous_cycle_record("2026-10-15").date == "2026-10-14"
    assert cycle_store.previous_cycle_record("2026-10-13") is None


def test_recent_cycle_records_excludes_current_date_and_sorts_ascending():
    for day in ("2026-10-13", "2026-10-14", "2026-10-15"):
        cycle_store.save_cycle_record(_record(day))

    before = cycle_store.recent_cycle_records(20, before="2026-10-15")
    assert [item.date for item in before] == ["2026-10-13", "2026-10-14"]

    without_bound = cycle_store.recent_cycle_records(20)
    assert [item.date for item in without_bound] == ["2026-10-13", "2026-10-14", "2026-10-15"]


def test_save_cycle_record_overwrites_same_date():
    cycle_store.save_cycle_record(_record("2026-10-15", stage="冰点"))
    cycle_store.save_cycle_record(_record("2026-10-15", stage="退潮杀跌"))

    assert cycle_store.load_cycle_record("2026-10-15").stage == "退潮杀跌"
    assert get_connection().execute("SELECT COUNT(*) FROM daily_review_cycle_records").fetchone()[0] == 1


def test_build_cycle_record_prefers_major_indices():
    snapshot = _snapshot(
        indices=[
            {"code": "399006", "name": "创业板指", "change_pct": -0.5},
            {"code": "000300", "name": "沪深300", "change_pct": 0.3},
        ],
    )
    record = cycle_store.build_cycle_record(date_text="2026-10-15", snapshot=snapshot)

    assert [item.name for item in record.indices] == ["创业板指"]


def test_build_cycle_record_tolerates_empty_snapshot():
    record = cycle_store.build_cycle_record(date_text="2026-10-15", snapshot=_snapshot())

    assert record.stage == ""
    assert record.indices == []
    assert record.limit_up_count is None
    assert record.break_rate is None
    assert record.up_down_ratio is None


# --- cycle_trend（情绪周期趋势） ------------------------------------------------


def test_cycle_trend_marks_transitions():
    trend = cycle_trend.build_cycle_trend(
        [
            _record("2026-10-13", stage="冰点"),
            _record("2026-10-14", stage="修复回暖"),
            _record("2026-10-15", stage="修复回暖"),
            _record("2026-10-16", stage="高位分化"),
        ]
    )

    assert [point.stage_transition for point in trend.points] == ["", "升级", "延续", "升级"]


def test_cycle_trend_marks_downgrade_and_switch():
    trend = cycle_trend.build_cycle_trend(
        [
            _record("2026-10-13", stage="主升共振"),
            _record("2026-10-14", stage="高位分化"),
            _record("2026-10-15", stage="高位分化"),
            _record("2026-10-16", stage="冰点"),
        ]
    )

    assert [point.stage_transition for point in trend.points] == ["", "升级", "延续", "切换"]


def test_cycle_trend_stage_stats_use_next_day_index_change():
    trend = cycle_trend.build_cycle_trend(
        [
            _record("2026-10-13", stage="主升共振", index_change_pct=-1.0),
            _record("2026-10-14", stage="主升共振", index_change_pct=2.0),
            _record("2026-10-15", stage="主升共振", index_change_pct=-0.5),
            _record("2026-10-16", stage="冰点", index_change_pct=3.0),
        ]
    )
    stats = {stat.stage: stat for stat in trend.stage_stats}

    main = stats["主升共振"]
    assert main.occurrences == 3
    # 三个主升共振交易日的次日指数分别为 +2.0%、-0.5%、+3.0%（最后一天由冰点日承接）。
    assert main.next_day_up_ratio == pytest.approx(2 / 3)
    assert main.avg_next_day_index_change_pct == pytest.approx(1.5)


def test_cycle_trend_notes_small_samples_and_limits_days():
    empty = cycle_trend.build_cycle_trend([])
    assert empty.points == []
    assert "暂无历史复盘样本" in empty.note

    single = cycle_trend.build_cycle_trend([_record("2026-10-15")])
    assert "仅有一个交易日样本" in single.note

    limited = cycle_trend.build_cycle_trend(
        [_record(f"2026-10-{day:02d}") for day in range(1, 11)],
        days=3,
    )
    assert [point.date for point in limited.points] == ["2026-10-08", "2026-10-09", "2026-10-10"]


def test_cycle_trend_fills_next_day_change_from_following_record():
    trend = cycle_trend.build_cycle_trend(
        [_record("2026-10-13", index_change_pct=1.0), _record("2026-10-14", index_change_pct=-0.25)]
    )

    assert trend.points[0].next_index_change_pct == pytest.approx(-0.25)
    assert trend.points[1].next_index_change_pct is None


# --- self_check（复盘自检闭环） --------------------------------------------------


@pytest.fixture
def _no_realtime(monkeypatch):
    calls: list[list[str]] = []

    async def _fake_realtime(codes: list[str]) -> dict[str, float]:
        calls.append(codes)
        return {}

    monkeypatch.setattr(self_check, "_realtime_stock_changes", _fake_realtime)
    return calls


def _patch_local_changes(monkeypatch, changes: dict[str, float]) -> None:
    async def _fake_local(codes: list[str], verified_date: date) -> dict[str, float]:
        return {code: changes[code] for code in codes if code in changes}

    monkeypatch.setattr(self_check, "_local_stock_changes", _fake_local)


async def test_self_check_counts_hits_and_misses(monkeypatch, _no_realtime):
    _patch_local_changes(monkeypatch, {"000001": 3.2, "600000": -2.0})
    record = _record(
        "2026-10-14",
        watchlist=[
            DailyReviewWatchItem(name="甲", code="000001", role="总龙头"),
            DailyReviewWatchItem(name="乙", code="600000", role="中军容量票"),
        ],
    )

    check = await self_check.build_previous_review_check(
        record,
        verified_date=date(2026, 10, 15),
        current_indices=[{"code": "000001", "name": "上证指数", "change_pct": 0.5}],
        current_limit_up_count=48,
    )

    assert check is not None
    assert check.hit_count == 1
    assert check.checked_count == 2
    assert check.hit_rate == pytest.approx(0.5)
    assert [item.hit for item in check.watchlist] == [True, False]
    assert check.limit_up_delta == 48 - 60
    assert _no_realtime == []


async def test_self_check_flags_limit_up(monkeypatch, _no_realtime):
    _patch_local_changes(monkeypatch, {"000001": 10.0})
    record = _record("2026-10-14", watchlist=[DailyReviewWatchItem(name="甲", code="000001")])

    check = await self_check.build_previous_review_check(
        record,
        verified_date=date(2026, 10, 15),
        current_indices=[],
        current_limit_up_count=None,
    )

    assert check.watchlist[0].limit_up is True
    assert check.watchlist[0].hit is True


async def test_self_check_marks_missing_quote_without_hallucinating(monkeypatch, _no_realtime):
    _patch_local_changes(monkeypatch, {})
    record = _record("2026-10-14", watchlist=[DailyReviewWatchItem(name="甲", code="000001")])

    check = await self_check.build_previous_review_check(
        record,
        verified_date=date(2026, 10, 15),
        current_indices=[],
        current_limit_up_count=None,
    )

    assert check.watchlist[0].missing is True
    assert check.checked_count == 0
    assert check.hit_rate is None
    assert "次日行情尚未入库" in check.note


async def test_self_check_uses_realtime_only_for_today(monkeypatch):
    realtime_calls: list[list[str]] = []

    async def _fake_realtime(codes: list[str]) -> dict[str, float]:
        realtime_calls.append(codes)
        return {code: 4.0 for code in codes}

    monkeypatch.setattr(self_check, "_realtime_stock_changes", _fake_realtime)
    _patch_local_changes(monkeypatch, {})
    record = _record("2026-10-14", watchlist=[DailyReviewWatchItem(name="甲", code="000001")])

    historical = await self_check.build_previous_review_check(
        record,
        verified_date=date(2026, 10, 15),
        current_indices=[],
        current_limit_up_count=None,
    )
    assert historical.watchlist[0].missing is True
    assert realtime_calls == []

    monkeypatch.setattr(self_check, "market_today", lambda: date(2026, 10, 15))
    today = await self_check.build_previous_review_check(
        record,
        verified_date=date(2026, 10, 15),
        current_indices=[],
        current_limit_up_count=None,
    )
    assert today.watchlist[0].change_pct == pytest.approx(4.0)
    assert realtime_calls == [["000001"]]


async def test_self_check_returns_none_without_previous_record():
    assert (
        await self_check.build_previous_review_check(
            None,
            verified_date=date(2026, 10, 15),
            current_indices=[],
            current_limit_up_count=None,
        )
        is None
    )


async def test_self_check_compares_index_moves(monkeypatch, _no_realtime):
    record = _record("2026-10-14", index_change_pct=1.0)

    check = await self_check.build_previous_review_check(
        record,
        verified_date=date(2026, 10, 15),
        current_indices=[{"code": "000001", "name": "上证指数", "change_pct": -0.5}],
        current_limit_up_count=None,
    )

    assert check.indices[0].previous_change_pct == pytest.approx(1.0)
    assert check.indices[0].change_pct == pytest.approx(-0.5)


# --- Prompt 接线 ----------------------------------------------------------------


def test_build_prompt_renders_self_check_and_trend():
    check = DailyReviewPreviousCheck(
        review_date="2026-10-14",
        verified_date="2026-10-15",
        watchlist=[DailyReviewWatchCheck(name="甲", code="000001", change_pct=3.2, hit=True)],
        hit_count=1,
        checked_count=1,
        hit_rate=1.0,
        previous_stage="修复回暖",
        limit_up_count=48,
        previous_limit_up_count=60,
        limit_up_delta=-12,
        indices=[
            DailyReviewIndexCheck(
                code="000001",
                name="上证指数",
                previous_change_pct=1.0,
                change_pct=-0.5,
            )
        ],
    )
    trend = cycle_trend.build_cycle_trend(
        [_record("2026-10-13", stage="冰点"), _record("2026-10-14", stage="修复回暖")]
    )

    prompt = review_builder.build_prompt(
        "2026-10-15",
        _snapshot(),
        MARKET_USER_PROMPT,
        previous_review_check=check,
        cycle_trend=trend,
    )

    assert "# 上一交易日复盘自检（2026-10-14 → 2026-10-15）" in prompt
    assert "甲(000001)：+3.20%（涨停）" not in prompt  # 3.2% 不是涨停
    assert "甲(000001)：+3.20%（上涨）" in prompt
    assert "观察标的命中：1/1" in prompt
    assert "涨停家数：60 → 48（-12）" in prompt
    assert "# 情绪周期历史趋势（最近 2 个交易日，按时间升序）" in prompt


def test_build_prompt_without_history_inputs_stays_explicit():
    prompt = review_builder.build_prompt("2026-10-15", _snapshot(), MARKET_USER_PROMPT)

    assert "暂无上一交易日复盘可对照" in prompt
    assert "暂无历史样本" in prompt


# --- API 路由 -------------------------------------------------------------------


async def test_get_cycle_trend_api_route():
    from httpx import ASGITransport, AsyncClient

    from app.api.auth.dependencies import require_active_user
    from app.main import app

    cycle_store.save_cycle_record(_record("2026-10-14", stage="冰点"))
    cycle_store.save_cycle_record(_record("2026-10-15", stage="修复回暖"))

    app.dependency_overrides[require_active_user] = lambda: {"id": 1, "username": "test", "is_admin": False}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/daily-review/cycle_trend?days=10")

        assert resp.status_code == 200
        data = resp.json()
        assert [p["date"] for p in data["points"]] == ["2026-10-14", "2026-10-15"]
        assert data["points"][1]["stage_transition"] == "升级"
    finally:
        app.dependency_overrides.pop(require_active_user, None)

