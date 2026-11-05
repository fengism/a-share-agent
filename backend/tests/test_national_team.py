import asyncio
import time
from datetime import date, datetime, timedelta

import pytest

from app.financial_data.market.quotes.national_team import (
    ETF_POOL,
    INDEX_POOL,
    build_national_team_response,
)


def test_etf_pool_and_index_pool_structure():
    assert "csi300" in INDEX_POOL
    assert "csi_a500" in INDEX_POOL
    assert "csi2000" in INDEX_POOL
    assert "dividend" in INDEX_POOL
    assert "star100" in INDEX_POOL

    assert INDEX_POOL["csi_a500"].category == "a500"
    assert INDEX_POOL["dividend"].category == "dividend"
    assert INDEX_POOL["csi2000"].category == "growth"
    assert INDEX_POOL["csi300"].category == "core_broad"

    # Verify key ETFs exist
    assert "560510" in ETF_POOL  # 国泰中证A500
    assert ETF_POOL["560510"].category == "a500"
    assert "512890" in ETF_POOL  # 红利低波
    assert ETF_POOL["512890"].category == "dividend"
    assert "563000" in ETF_POOL  # 中证2000
    assert ETF_POOL["563000"].category == "growth"
    assert len(ETF_POOL) == 22


def test_build_national_team_response_daily_flows():
    # Construct minimal share and close histories
    dates = ["2026-09-15", "2026-09-16"]
    share_history = {
        "510300": {"2026-09-15": 100_000_000, "2026-09-16": 120_000_000},
        "560510": {"2026-09-15": 50_000_000, "2026-09-16": 60_000_000},
    }
    etf_close_history = {
        "510300": {"2026-09-15": 3.5, "2026-09-16": 3.6},
        "560510": {"2026-09-15": 1.0, "2026-09-16": 1.0},
    }
    index_close_history = {
        "csi300": {"2026-09-15": 3800.0, "2026-09-16": 3850.0},
        "csi_a500": {"2026-09-15": 4200.0, "2026-09-16": 4250.0},
    }
    etf_amount_history = {
        "510300": {"2026-09-15": 10.0, "2026-09-16": 15.0},
        "560510": {"2026-09-15": 2.0, "2026-09-16": 3.0},
    }

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=etf_close_history,
        etf_amount_history=etf_amount_history,
        index_close_history=index_close_history,
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    assert response.as_of_date == "2026-09-16"
    assert len(response.daily_flows) == 2
    # Second day (2026-09-16) flow:
    # 510300: (120M - 100M) = 20M shares = 0.2 亿份 * 3.6 = 0.72 亿元
    # 560510: (60M - 50M) = 10M shares = 0.1 亿份 * 1.0 = 0.1 亿元
    flow_pt = response.daily_flows[1]
    assert flow_pt.date == "2026-09-16"
    assert flow_pt.total_flow_100m == pytest.approx(0.82)
    assert flow_pt.total_shares_change_100m == pytest.approx(0.3)
    assert flow_pt.total_amount_100m == pytest.approx(18.0)
    assert flow_pt.cumulative_flow_100m == pytest.approx(0.82)
    assert flow_pt.benchmark_close == pytest.approx(3850.0)
    assert flow_pt.flows_by_index.get("沪深300") == pytest.approx(0.72)
    assert flow_pt.flows_by_index.get("中证A500") == pytest.approx(0.1)
    assert flow_pt.flows_by_category.get("core_broad") == pytest.approx(0.72)
    assert flow_pt.flows_by_category.get("a500") == pytest.approx(0.1)
    assert response.summary.total_amount_1d_100m == pytest.approx(18.0)
    assert response.summary.cumulative_net_flow_100m == pytest.approx(0.82)
    assert response.summary.ytd_net_flow_100m == pytest.approx(0.82)
    assert response.summary.top_flow_category == "core_broad"
    assert response.summary.top_flow_index == "沪深300"


def test_build_national_team_response_support_score_and_zones():
    dates = ["2026-09-15", "2026-09-16"]
    share_history = {
        code: {"2026-09-15": 100_000_000, "2026-09-16": 120_000_000}
        for code in ["510300", "510310", "510330", "159919"]
    }
    share_history["560510"] = {"2026-09-15": 50_000_000, "2026-09-16": 60_000_000}
    etf_close_history = {
        code: {"2026-09-15": 3.5, "2026-09-16": 3.6}
        for code in ["510300", "510310", "510330", "159919"]
    }
    etf_close_history["560510"] = {"2026-09-15": 1.0, "2026-09-16": 1.0}
    index_close_history = {
        "csi300": {"2026-09-15": 3800.0, "2026-09-16": 3850.0},
        "csi_a500": {"2026-09-15": 4200.0, "2026-09-16": 4250.0},
    }

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=etf_close_history,
        index_close_history=index_close_history,
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    assert response.support_score is not None
    assert 0 <= response.support_score.score <= 100
    assert response.support_score.status in ["neutral", "moderate", "active", "strong"]
    assert len(response.milestones) >= 5
    assert len(response.support_zones) >= 1
    csi300_zone = next(z for z in response.support_zones if z.index_key == "csi300")
    assert csi300_zone.current_price == 3850.0
    assert csi300_zone.weighted_avg_cost == 3850.0
    assert csi300_zone.cost_buffer_pct == 0.0


def test_build_national_team_response_portrait_and_volume_anomaly():
    dates = ["2026-09-15", "2026-09-16"]
    share_history = {
        "510300": {"2026-09-15": 100_000_000, "2026-09-16": 120_000_000},
    }
    etf_close_history = {
        "510300": {"2026-09-15": 3.5, "2026-09-16": 3.6},
    }
    index_close_history = {
        "csi300": {"2026-09-15": 3800.0, "2026-09-16": 3850.0},
    }
    # 510300 day 1 amount = 5.0 亿, day 2 amount = 15.0 亿 (ratio 3.0x >= 1.8x, amount >= 5.0 -> abnormal volume)
    etf_amount_history = {
        "510300": {"2026-09-15": 5.0, "2026-09-16": 15.0},
    }

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=etf_close_history,
        index_close_history=index_close_history,
        etf_amount_history=etf_amount_history,
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    # Portrait assertions
    assert response.portrait is not None
    assert len(response.portrait.entities) == 3
    assert any(e.short_name == "中央汇金" for e in response.portrait.entities)
    assert len(response.portrait.industry_allocations) == 6
    assert any(ia.industry == "银行金融" for ia in response.portrait.industry_allocations)
    assert len(response.portrait.top_holdings) == 10
    assert response.portrait.top_holdings[0].name == "工商银行"

    # Volume anomaly assertions
    etf_510300 = next(e for e in response.etfs if e.code == "510300")
    assert etf_510300.latest_amount_100m == pytest.approx(15.0)
    assert etf_510300.volume_ratio == pytest.approx(3.0)
    assert etf_510300.is_abnormal_volume is True
    assert etf_510300.points[0].amount_100m == pytest.approx(5.0)
    assert etf_510300.points[1].amount_100m == pytest.approx(15.0)



def test_index_series_keeps_latest_day_when_a_member_is_missing():
    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    share_history = {
        code: {dates[0]: 100_000_000, dates[1]: 110_000_000}
        for code in members
    }
    # 深交所成员缺最新一天，旧实现会把整条指数的最新点位一起丢掉。
    share_history["159919"] = {dates[0]: 100_000_000}
    close_history = {code: {dates[0]: 3.5, dates[1]: 3.6} for code in members}

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=close_history,
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    csi300 = next(item for item in response.indices if item.index_key == "csi300")
    assert csi300.latest_date == dates[1]
    assert [point.date for point in csi300.points] == dates
    assert csi300.latest_change_1d_100m == pytest.approx(0.3)
    assert csi300.points[-1].covered_etf_count == 3
    assert csi300.points[-1].total_etf_count == 4
    assert csi300.points[-1].coverage_ratio == pytest.approx(0.75)
    assert csi300.coverage_ratio == pytest.approx(0.75)


def test_summary_sums_available_values_instead_of_returning_none():
    dates = ["2026-09-15", "2026-09-16"]
    share_history = {
        "510300": {dates[0]: 100_000_000, dates[1]: 110_000_000},
        # 新上市 ETF 只有最新一天，不能把整体 KPI 拖成 None。
        "510050": {dates[1]: 50_000_000},
    }
    close_history = {
        "510300": {dates[0]: 3.5, dates[1]: 3.6},
        "510050": {dates[1]: 2.0},
    }

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=close_history,
        index_close_history={},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    assert response.summary.total_shares_100m == pytest.approx(1.6)
    assert response.summary.change_1d_100m == pytest.approx(0.1)
    assert response.summary.coverage_ratio == pytest.approx(round(2 / len(ETF_POOL), 4))
    assert response.summary.quality == "partial"


def test_default_portrait_is_marked_as_static_reference():
    response = build_national_team_response(
        share_history={},
        etf_close_history={},
        index_close_history={},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=["2026-09-16"],
    )

    assert response.portrait.is_static is True
    assert response.portrait.as_of == "2024-12-31"
    assert "静态" in response.portrait.source


def test_support_zones_are_sorted_by_price_even_when_dates_descend():
    dates = ["2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13"]
    members = ["510300", "510310", "510330", "159919"]
    share_history = {
        code: {day: 100_000_000 + index * 10_000_000 for index, day in enumerate(dates)}
        for code in members
    }
    close_history = {code: {day: 3.5 for day in dates} for code in members}
    index_closes = {dates[0]: 4000.0, dates[1]: 3000.0, dates[2]: 2000.0, dates[3]: 1000.0}

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=close_history,
        index_close_history={"csi300": index_closes},
        fetched_at="2026-09-13T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    csi300 = next(item for item in response.support_zones if item.index_key == "csi300")
    labels = [zone.range_label for zone in csi300.zones]
    assert labels[0].startswith("<")
    assert labels[-1].startswith("≥")
    assert labels == sorted(labels, key=lambda label: float("-inf") if label.startswith("<") else float(label.lstrip("≥").split("-")[0]))


def test_national_team_snapshot_reports_refresh_counters():
    from app.financial_data.market.quotes.national_team import (
        _record_collection,
        _record_source_failure,
        national_team_snapshot,
    )

    before = national_team_snapshot()
    started = time.monotonic()
    response = build_national_team_response(
        share_history={},
        etf_close_history={},
        index_close_history={},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=["2026-09-16"],
    )
    _record_collection("test-trigger", started=started, response=response)
    _record_collection("test-trigger", started=started, error=RuntimeError("boom"))
    _record_source_failure("sse")

    after = national_team_snapshot()
    assert after["attempts_total"] == before["attempts_total"] + 2  # type: ignore[operator]
    assert after["failures_total"] == before["failures_total"] + 1  # type: ignore[operator]
    trigger_counts = after["by_trigger"]["test-trigger"]  # type: ignore[index]
    assert trigger_counts["attempts"] - before["by_trigger"].get("test-trigger", {}).get("attempts", 0) == 2  # type: ignore[index,union-attr]
    assert after["last_error"] == "RuntimeError"
    # 只记异常类名，避免把上游消息里的 URL / 参数带进 /metrics。
    assert "boom" not in str(after["last_error"])
    assert after["source_failures"]["sse"] >= 1  # type: ignore[index]


def test_refresh_skips_outside_after_close_window(monkeypatch):
    from app.core.timezones import SHANGHAI_TIMEZONE
    from app.financial_data.market.quotes import national_team as nt

    async def fail_if_called(*_, **__):
        raise AssertionError("窗口外不应触发采集")

    monkeypatch.setattr(nt, "_shared_response", fail_if_called)
    monkeypatch.setattr(nt, "_load_expected_trading_dates", fail_if_called)

    before_open = datetime(2026, 9, 16, 10, 30, tzinfo=SHANGHAI_TIMEZONE)
    assert asyncio.run(nt.refresh_national_team_after_close(now=before_open)) == "skipped_before_close"

    late_night = datetime(2026, 9, 16, 19, 0, tzinfo=SHANGHAI_TIMEZONE)
    assert asyncio.run(nt.refresh_national_team_after_close(now=late_night)) == "skipped_after_window"


def test_refresh_skips_non_trading_day(monkeypatch):
    from app.core.timezones import SHANGHAI_TIMEZONE
    from app.financial_data.market.quotes import national_team as nt

    async def no_trading_day(start, now):
        return (["2026-09-14", "2026-09-15"], False)

    async def fail_if_called(*_, **__):
        raise AssertionError("非交易日不应触发采集")

    monkeypatch.setattr(nt, "_load_expected_trading_dates", no_trading_day)
    monkeypatch.setattr(nt, "_shared_response", fail_if_called)
    monkeypatch.setitem(nt._refresh_metrics, "scheduled_completed_date", "")

    moment = datetime(2026, 9, 16, 16, 30, tzinfo=SHANGHAI_TIMEZONE)
    assert asyncio.run(nt.refresh_national_team_after_close(now=moment)) == "skipped_not_trading_day"


def test_refresh_marks_complete_only_when_as_of_date_matches(monkeypatch):
    from app.core.timezones import SHANGHAI_TIMEZONE
    from app.financial_data.market.quotes import national_team as nt

    day = "2026-09-16"
    # 交易所份额发布常晚于 16:00：as_of 还停在昨天时必须判定为「未完成」，
    # 否则当天永远不会再补一次。
    partial = build_national_team_response(
        share_history={"510300": {"2026-09-15": 100_000_000}},
        etf_close_history={"510300": {"2026-09-15": 3.5}},
        index_close_history={},
        fetched_at="2026-09-16T16:10:00+08:00",
        requested_days=30,
        expected_trading_dates=["2026-09-15", day],
    )
    completed = build_national_team_response(
        share_history={code: {"2026-09-15": 100_000_000, day: 100_000_000} for code in nt.ETF_POOL},
        etf_close_history={code: {"2026-09-15": 3.5, day: 3.5} for code in nt.ETF_POOL},
        index_close_history={key: {"2026-09-15": 3500.0, day: 3500.0} for key in nt.INDEX_POOL},
        fetched_at="2026-09-16T17:10:00+08:00",
        requested_days=30,
        expected_trading_dates=["2026-09-15", day],
    )
    responses = [partial, completed]

    async def trading_day(start, now):
        return (["2026-09-15", day], False)

    async def fake_response(*_, **__):
        return responses.pop(0)

    monkeypatch.setattr(nt, "_load_expected_trading_dates", trading_day)
    monkeypatch.setattr(nt, "_shared_response", fake_response)
    monkeypatch.setitem(nt._refresh_metrics, "scheduled_completed_date", "")

    moment = datetime(2026, 9, 16, 16, 30, tzinfo=SHANGHAI_TIMEZONE)
    assert asyncio.run(nt.refresh_national_team_after_close(now=moment)) == "retry_partial"
    assert nt._refresh_metrics["scheduled_completed_date"] == ""
    assert asyncio.run(nt.refresh_national_team_after_close(now=moment)) == "refreshed"
    assert nt._refresh_metrics["scheduled_completed_date"] == day
    # 同一业务日完成后不再重复采集。
    assert asyncio.run(nt.refresh_national_team_after_close(now=moment)) == "skipped_completed"


def test_refresh_force_bypasses_response_cache(monkeypatch):
    from app.financial_data.market.quotes import national_team as nt

    calls: list[tuple[str, bool]] = []

    async def fake_collect(days, *, trigger="request", force=False):
        calls.append((trigger, force))
        return build_national_team_response(
            share_history={},
            etf_close_history={},
            index_close_history={},
            fetched_at="2026-09-16T17:00:00+08:00",
            requested_days=30,
            expected_trading_dates=["2026-09-16"],
        )

    monkeypatch.setattr(nt, "_collect_response", fake_collect)
    # 缓存里有旧值也不能被复用，否则定时刷新等于没刷。
    nt.market_cache.set(nt._response_cache_key(120), {"stale": True}, ttl=600)

    asyncio.run(nt._shared_response(120, trigger="scheduled", force=True))

    assert calls == [("scheduled", True)]


def test_lifecycle_registers_after_close_refresh_task() -> None:
    """收盘后刷新必须真的挂在生命周期上，且不能被误接到 readiness。"""
    import inspect
    from unittest.mock import MagicMock

    from app.runtime import lifecycle

    params = inspect.signature(lifecycle.build_background_task_specs).parameters
    assert "national_team_snapshot_refresh" in params
    assert "national_team_snapshot_refresh" in inspect.signature(lifecycle.application_lifespan).parameters

    specs = lifecycle.build_background_task_specs(**{name: MagicMock() for name in params})
    spec = next(item for item in specs if item.name == "national_team_snapshot_refresh")

    assert spec.long_running is True
    assert spec.restart_on_exit is True
    # 行情刷新挂了不影响 HTTP 请求，接 readiness 会让一次抖动摘掉全部流量。
    assert spec.readiness_required is False
    assert spec.critical is False


def test_without_etf_points_keeps_aggregation_and_scalars():
    """裁剪 ETF points 只能影响序列本身，绝不能改变汇总口径或标量字段。"""
    from app.financial_data.market.quotes.national_team import without_etf_points

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    share_history = {code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members}
    close_history = {code: {dates[0]: 3.5, dates[1]: 3.6} for code in members}
    amount_history = {code: {dates[0]: 10.0, dates[1]: 20.0} for code in members}

    full = build_national_team_response(
        share_history=share_history,
        etf_close_history=close_history,
        etf_amount_history=amount_history,
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )
    trimmed = without_etf_points(full)

    assert full.etf_points_included is True
    assert trimmed.etf_points_included is False
    assert all(item.points == [] for item in trimmed.etfs)
    # 原始响应不能被就地改写（它同时被写进缓存）。
    assert all(item.points for item in full.etfs if item.code in members)

    # 汇总、资金流、评分、点位分布与指数序列必须完全一致。
    assert trimmed.summary == full.summary
    assert trimmed.support_score == full.support_score
    assert trimmed.support_zones == full.support_zones
    assert [flow.total_flow_100m for flow in trimmed.daily_flows] == [
        flow.total_flow_100m for flow in full.daily_flows
    ]
    assert [item.points for item in trimmed.indices] == [item.points for item in full.indices]

    # 表格与 CSV 依赖的标量必须一个不少。
    for original, stripped in zip(full.etfs, trimmed.etfs, strict=True):
        assert stripped.latest_shares_100m == original.latest_shares_100m
        assert stripped.latest_change_1d_100m == original.latest_change_1d_100m
        assert stripped.change_20d_100m == original.change_20d_100m
        assert stripped.latest_amount_100m == original.latest_amount_100m
        assert stripped.volume_ratio == original.volume_ratio
        assert stripped.is_abnormal_volume == original.is_abnormal_volume
        # 净申购改成标量字段，前端不必再读 points[-1]。
        assert stripped.latest_estimated_net_flow_100m == original.latest_estimated_net_flow_100m

    member = next(item for item in trimmed.etfs if item.code == "510300")
    # 0.1 亿份 × 3.6 元
    assert member.latest_estimated_net_flow_100m == pytest.approx(0.36)
    assert member.points == []


def test_get_national_team_holdings_trims_only_when_asked(monkeypatch):
    """缓存里存完整响应，include_etf_points 只影响这一次序列化。"""
    from app.financial_data.market.quotes import national_team as nt

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    async def fake_resolve(days):
        return full.model_copy(deep=True)

    monkeypatch.setattr(nt, "_resolve_response", fake_resolve)

    stripped = asyncio.run(nt.get_national_team_etf_holdings(120, include_etf_points=False))
    kept = asyncio.run(nt.get_national_team_etf_holdings(120))

    assert any(item.points for item in kept.etfs)
    assert all(item.points == [] for item in stripped.etfs)
    assert stripped.summary.total_shares_100m == kept.summary.total_shares_100m


def test_support_score_confidence_reflects_coverage_and_freshness():
    from app.financial_data.market.quotes.national_team import ETF_POOL, INDEX_POOL

    dates = ["2026-09-15", "2026-09-16"]

    def build(*, expected_dates, codes):
        return build_national_team_response(
            share_history={
                code: {dates[0]: 100_000_000, dates[1]: 110_000_000}
                for code in codes
            },
            etf_close_history={
                code: {dates[0]: 3.5, dates[1]: 3.6}
                for code in codes
            },
            index_close_history={
                key: {dates[0]: 3500.0, dates[1]: 3520.0}
                for key in INDEX_POOL
            },
            fetched_at="2026-09-16T18:00:00+08:00",
            requested_days=30,
            expected_trading_dates=expected_dates,
        )

    complete = build(expected_dates=dates, codes=list(ETF_POOL))
    assert complete.summary.coverage_ratio == pytest.approx(1.0)
    assert complete.support_score.confidence == pytest.approx(1.0)
    # 分数本身不受置信度影响。
    assert complete.support_score.score > 0

    # 份额停在上一交易日：评的是“昨天”的盘面。
    stale = build(expected_dates=[*dates, "2026-09-17"], codes=list(ETF_POOL))
    assert stale.stale is True
    assert stale.support_score.confidence == pytest.approx(0.35)

    # 只有两只 ETF 有数据：覆盖不足，置信度应显著降低。
    sparse = build(expected_dates=dates, codes=["510300", "510310"])
    assert sparse.summary.coverage_ratio < 0.2
    assert sparse.support_score.confidence < 0.2


def _http_request(headers: list[tuple[bytes, bytes]] | None = None):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/market/national-team-etf-holdings",
            "raw_path": b"/api/market/national-team-etf-holdings",
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
    )


def test_national_team_route_sets_etag_and_returns_304(monkeypatch):
    from starlette.responses import Response

    from app.api.routes.market_sections import quotes as quotes_route

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    payload = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )
    seen: list[bool] = []

    async def fake_service(days, *, include_etf_points=True, include_index_points=True, include_flow_breakdown=True):
        seen.append((include_etf_points, include_index_points, include_flow_breakdown))
        return payload

    monkeypatch.setattr(quotes_route, "get_national_team_etf_holdings_service", fake_service)

    response = Response()
    result = asyncio.run(
        quotes_route.get_national_team_etf_holdings(
            _http_request(), response, days=120, include_etf_points=False, include_index_points=True, include_flow_breakdown=True
        )
    )
    assert result is payload
    assert seen == [(False, True, True)]
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')
    assert response.headers["cache-control"].startswith("private, max-age=")

    not_modified = asyncio.run(
        quotes_route.get_national_team_etf_holdings(
            _http_request([(b"if-none-match", etag.encode())]),
            Response(),
            days=120,
            include_etf_points=False,
            include_index_points=True,
            include_flow_breakdown=True,
        )
    )
    assert isinstance(not_modified, Response)
    assert not_modified.status_code == 304
    assert not_modified.headers["etag"] == etag
    # 304 也必须带缓存头，否则中间缓存会以为不可缓存。
    assert "cache-control" in not_modified.headers


def test_national_team_etag_matches_weak_and_comma_separated_values():
    from app.api.routes.market_sections.quotes import _etag_matches

    etag = '"abc123"'
    assert _etag_matches(None, etag) is False
    assert _etag_matches(etag, etag) is True
    assert _etag_matches(f'"other", {etag}', etag) is True
    assert _etag_matches(f'W/{etag}', etag) is True
    assert _etag_matches("*", etag) is True
    assert _etag_matches('"different"', etag) is False


def test_national_team_cache_control_shortens_when_partial():
    from app.api.routes.market_sections.quotes import _national_team_cache_control

    dates = ["2026-09-15", "2026-09-16"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in ETF_POOL},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in ETF_POOL},
        index_close_history={key: {dates[0]: 3500.0, dates[1]: 3520.0} for key in INDEX_POOL},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )
    assert _national_team_cache_control(full) == "private, max-age=300"

    partial = full.model_copy(update={"partial": True})
    assert _national_team_cache_control(partial) == "private, max-age=60"


def test_support_score_history_replays_each_day_with_same_factors():
    from app.financial_data.market.quotes.national_team import ETF_POOL, INDEX_POOL

    dates = ["2026-09-14", "2026-09-15", "2026-09-16"]
    shares = {code: {dates[0]: 100_000_000, dates[1]: 105_000_000, dates[2]: 115_000_000} for code in ETF_POOL}
    closes = {code: {dates[0]: 3.4, dates[1]: 3.5, dates[2]: 3.6} for code in ETF_POOL}
    response = build_national_team_response(
        share_history=shares,
        etf_close_history=closes,
        index_close_history={
            key: {dates[0]: 3400.0, dates[1]: 3450.0, dates[2]: 3420.0} for key in INDEX_POOL
        },
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    history = response.support_score_history
    assert [point.date for point in history] == dates
    # 最新一天的历史分必须与实时分一致：两套路径不能算出不同结论。
    assert history[-1].score == response.support_score.score
    assert history[-1].status == response.support_score.status
    assert history[-1].confidence == response.support_score.confidence
    assert all(0.0 <= point.score <= 100.0 for point in history)
    assert all(0.0 <= point.confidence <= 1.0 for point in history)
    # 应该是随时间变化的曲线，而不是把今天的分数向前填充。
    assert len({point.score for point in history}) > 1


def test_daily_flows_keep_early_days_when_a_member_stops_updating():
    """某只 ETF 最新一天缺失时，它之前的真实资金流不应被一起抹掉。"""
    dates = ["2026-09-14", "2026-09-15", "2026-09-16"]
    share_history = {
        "510300": {dates[0]: 100_000_000, dates[1]: 110_000_000, dates[2]: 120_000_000},
        "510310": {dates[0]: 100_000_000, dates[1]: 110_000_000},
        "510330": {dates[0]: 100_000_000, dates[1]: 110_000_000, dates[2]: 120_000_000},
        "159919": {dates[0]: 100_000_000, dates[1]: 110_000_000, dates[2]: 120_000_000},
    }
    close_history = {
        code: {dates[0]: 3.4, dates[1]: 3.5, dates[2]: 3.6} for code in share_history
    }
    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=close_history,
        index_close_history={"csi300": {dates[0]: 3700.0, dates[1]: 3800.0, dates[2]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    # 第二天四只 ETF 都有 0.1 亿份的增量，全部应计入。
    assert response.daily_flows[1].total_flow_100m == pytest.approx(4 * 0.1 * 3.5)
    # 第三天 510310 没有数据，只汇总剩下三只。
    assert response.daily_flows[2].total_flow_100m == pytest.approx(3 * 0.1 * 3.6)
    assert response.covered_etf_count == 3
    assert response.support_score_history[1].coverage_ratio == pytest.approx(0.1818)
    assert response.support_score_history[2].coverage_ratio == pytest.approx(0.1364)


def test_overview_strips_series_and_caps_history():
    from app.financial_data.market.quotes.national_team import build_national_team_overview

    dates = [f"2026-08-{day:02d}" for day in range(1, 32)] + [
        f"2026-09-{day:02d}" for day in range(1, 32)
    ]
    members = ["510300", "510310", "510330", "159919"]
    response = build_national_team_response(
        share_history={
            code: {day: 100_000_000 + index * 1_000_000 for index, day in enumerate(dates)}
            for code in members
        },
        etf_close_history={code: {day: 3.5 for day in dates} for code in members},
        index_close_history={"csi300": {day: 3800.0 for day in dates}},
        fetched_at="2026-09-30T18:00:00+08:00",
        requested_days=60,
        expected_trading_dates=dates,
    )

    overview = build_national_team_overview(response, history_days=10)

    assert len(overview.support_score_history) == 10
    assert overview.support_score_history[-1].date == response.support_score_history[-1].date
    assert overview.support_score.score == response.support_score.score
    assert overview.summary.total_shares_100m == response.summary.total_shares_100m
    assert overview.covered_etf_count == response.covered_etf_count
    assert overview.disclaimer == response.disclaimer

    # 概览必须与缓存里的完整响应脱钩，改它不能反向污染缓存对象。
    overview.summary.total_shares_100m = 0.0
    assert response.summary.total_shares_100m != 0.0


def test_get_national_team_overview_reuses_full_response(monkeypatch):
    from app.financial_data.market.quotes import national_team as nt

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )
    calls: list[int] = []

    async def fake_resolve(days):
        calls.append(days)
        return full

    monkeypatch.setattr(nt, "_resolve_response", fake_resolve)

    overview = asyncio.run(nt.get_national_team_overview(120))
    assert calls == [120]
    assert overview.support_score.score == full.support_score.score


def test_build_support_backtest_uses_future_closes():
    from app.financial_data.market.quotes.national_team import build_support_backtest

    rows = [
        {
            "date": f"2026-01-{index + 1:02d}",
            "status": "active" if index % 2 == 0 else "moderate",
            # 每日 +1 点，5 日 = +5%，20 日 = +20%。
            "csi300_close": 100.0 + index,
        }
        for index in range(30)
    ]

    result = build_support_backtest(rows, window_samples=365)

    def mean_return(horizon: int, predicate=lambda index: True) -> float:
        values = [
            ((100.0 + index + horizon) / (100.0 + index) - 1) * 100
            for index in range(len(rows) - horizon)
            if predicate(index)
        ]
        return sum(values) / len(values)

    assert result.sample_days == 30
    assert result.as_of_date == "2026-01-30"
    five, twenty = result.horizons
    assert (five.days, five.samples) == (5, 25)
    assert five.avg_return_pct == pytest.approx(mean_return(5), abs=0.01)
    assert five.win_rate_pct == pytest.approx(100.0)
    assert (twenty.days, twenty.samples) == (20, 10)
    assert twenty.avg_return_pct == pytest.approx(mean_return(20), abs=0.01)

    by_status = {item.status: item for item in result.by_status}
    assert set(by_status) == {"neutral", "moderate", "active", "strong"}
    assert by_status["active"].samples == 5
    assert by_status["active"].avg_return_20d_pct == pytest.approx(
        mean_return(20, lambda index: index % 2 == 0), abs=0.01
    )
    assert by_status["neutral"].samples == 0
    assert by_status["neutral"].avg_return_20d_pct is None


def test_build_support_backtest_skips_missing_closes_and_flags_small_samples():
    from app.financial_data.market.quotes.national_team import build_support_backtest

    rows = [
        {"date": f"2026-02-{index + 1:02d}", "status": "active", "csi300_close": None if index == 3 else 100.0 + index}
        for index in range(10)
    ]

    result = build_support_backtest(rows, window_samples=365)

    assert result.sample_days == 9
    assert result.horizons[0].samples == 4  # 只有 9 个有效收盘，5 日样本 4 个
    assert "样本不足" in result.note


def test_support_score_rows_pair_csi300_close():
    from app.financial_data.market.quotes.national_team import _support_score_rows

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    response = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    rows = _support_score_rows(response)

    assert [row[0] for row in rows] == dates
    assert rows[-1][5] == pytest.approx(3850.0)
    assert rows[-1][1] == response.support_score_history[-1].score


def test_without_index_points_keeps_scalars_and_other_series():
    from app.financial_data.market.quotes.national_team import without_index_points

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    trimmed = without_index_points(full)

    assert trimmed.index_points_included is False
    assert all(item.points == [] for item in trimmed.indices)
    assert any(item.points for item in full.indices)
    for original, stripped in zip(full.indices, trimmed.indices, strict=True):
        assert stripped.index_key == original.index_key
        assert stripped.latest_date == original.latest_date
        assert stripped.latest_change_1d_100m == original.latest_change_1d_100m
        assert stripped.change_5d_100m == original.change_5d_100m
        assert stripped.estimated_net_flow_1d_100m == original.estimated_net_flow_1d_100m
        assert stripped.coverage_ratio == original.coverage_ratio
    # 其它序列不能被连带清空。
    assert trimmed.summary == full.summary
    assert trimmed.daily_flows == full.daily_flows
    assert trimmed.support_score == full.support_score
    assert trimmed.support_zones == full.support_zones


def test_get_national_team_index_series_reuses_full_response(monkeypatch):
    from app.financial_data.market.quotes import national_team as nt

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    async def fake_resolve(days):
        assert days == 120
        return full

    monkeypatch.setattr(nt, "_resolve_response", fake_resolve)

    indices = asyncio.run(nt.get_national_team_index_series(120))
    assert indices is full.indices
    assert any(item.points for item in indices)


def test_without_flow_breakdown_keeps_totals_and_categories():
    from app.financial_data.market.quotes.national_team import without_flow_breakdown

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    trimmed = without_flow_breakdown(full)

    assert trimmed.flow_breakdown_included is False
    assert all(flow.flows_by_index == {} for flow in trimmed.daily_flows)
    assert any(flow.flows_by_index for flow in full.daily_flows)
    assert [flow.total_flow_100m for flow in trimmed.daily_flows] == [
        flow.total_flow_100m for flow in full.daily_flows
    ]
    assert [flow.flows_by_category for flow in trimmed.daily_flows] == [
        flow.flows_by_category for flow in full.daily_flows
    ]


def test_get_national_team_index_series_item_filters_and_returns_none(monkeypatch):
    from app.financial_data.market.quotes import national_team as nt

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    async def fake_resolve(days):
        assert days == 120
        return full

    monkeypatch.setattr(nt, "_resolve_response", fake_resolve)

    item = asyncio.run(nt.get_national_team_index_series_item("csi300", 120))
    assert item is not None
    assert item.index_key == "csi300"
    assert item.points
    assert asyncio.run(nt.get_national_team_index_series_item("nope", 120)) is None


def test_score_percentile_needs_minimum_samples():
    from app.financial_data.market.quotes.national_team_aggregation import _score_percentile
    from app.financial_data.market.quotes.schemas import NationalTeamSupportHistoryPoint

    history = [
        NationalTeamSupportHistoryPoint(
            date=f"2026-09-{index + 1:02d}", score=float(index), status="neutral", confidence=0.9
        )
        for index in range(60)
    ]

    assert _score_percentile(history, 59.0) == pytest.approx(99.2)
    assert _score_percentile(history, 29.5) == pytest.approx(50.0)
    assert _score_percentile(history, 0.0) == pytest.approx(0.8)
    # 全平时是 50 分位，而不是 100。
    flat = [
        NationalTeamSupportHistoryPoint(
            date=f"2026-10-{index + 1:02d}", score=60.0, status="active", confidence=0.9
        )
        for index in range(60)
    ]
    assert _score_percentile(flat, 60.0) == pytest.approx(50.0)
    # 少于 60 个样本不硬凑 60 日分位。
    assert _score_percentile(history[:59], 58.0) is None


def test_build_response_fills_score_percentile_when_history_is_enough():
    from app.financial_data.market.quotes.national_team import ETF_POOL, INDEX_POOL

    dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(70)]
    members = list(ETF_POOL)
    response = build_national_team_response(
        share_history={
            code: {day: 100_000_000 + index * 5_000_000 for index, day in enumerate(dates)}
            for code in members
        },
        etf_close_history={code: {day: 3.5 for day in dates} for code in members},
        index_close_history={key: {day: 3500.0 + index * 10 for index, day in enumerate(dates)} for key in INDEX_POOL},
        fetched_at="2026-09-12T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    assert response.support_score.percentile_60d is not None
    assert 0.0 <= response.support_score.percentile_60d <= 100.0


def test_support_score_store_upserts_and_keeps_known_close():
    from app.infrastructure.persistence import national_team_etf_store as store

    dates = ["2099-01-01", "2099-01-02", "2099-01-03"]
    store.save_support_scores(
        [
            (dates[0], 40.0, "moderate", 0.9, 1.0, 3500.0),
            (dates[1], 55.0, "moderate", 0.9, 1.0, 3550.0),
            (dates[2], 70.0, "active", 0.8, 0.9, 3600.0),
        ]
    )

    rows = store.load_support_scores(since=dates[0])
    ours = [row for row in rows if row["date"] in dates]
    assert [row["date"] for row in ours] == dates
    assert ours[1]["score"] == pytest.approx(55.0)
    assert ours[2]["csi300_close"] == pytest.approx(3600.0)

    # 同日重算但当天没有指数收盘：不能把已知收盘抹掉。
    store.save_support_scores([(dates[1], 58.0, "moderate", 0.95, 1.0, None)])
    updated = {row["date"]: row for row in store.load_support_scores(since=dates[0])}
    assert updated[dates[1]]["score"] == pytest.approx(58.0)
    assert updated[dates[1]]["confidence"] == pytest.approx(0.95)
    assert updated[dates[1]]["csi300_close"] == pytest.approx(3550.0)

    # 只取最近 N 条时按日期升序返回尾部。
    assert [row["date"] for row in store.load_support_scores(since=dates[0], limit=2)] == dates[1:]

    with pytest.raises(ValueError):
        store.save_support_scores([("2099-01-04", 50.0, "unknown", 0.9, 1.0, None)])


def test_missing_breadth_is_neutral_not_zero():
    """当天分类资金流尚未出来时，扩散因子应给中性分而不是 0。"""
    dates = ["2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    response = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )

    assert response.daily_flows[-1].total_flow_100m is None
    assert response.support_score.breadth_factor == pytest.approx(15.0)


def test_backtest_filters_low_confidence_and_coverage():
    from app.financial_data.market.quotes.national_team import build_support_backtest

    rows = [
        {
            "date": f"2026-03-{index + 1:02d}",
            "status": "active",
            "confidence": 0.9,
            "coverage_ratio": 1.0,
            "csi300_close": 100.0 + index,
        }
        for index in range(30)
    ]
    for row in rows[:5]:
        row["confidence"] = 0.2
    for row in rows[5:9]:
        row["coverage_ratio"] = 0.2

    result = build_support_backtest(rows, window_samples=365)

    assert result.excluded_low_confidence == 5
    assert result.excluded_low_coverage == 4
    assert result.sample_days == 21
    assert result.first_sample_date == rows[9]["date"]
    assert result.last_sample_date == rows[-1]["date"]
    assert result.horizons[1].samples == 1
    assert "20 日样本不足" in result.note


def test_overview_and_backtest_routes_support_conditional_requests(monkeypatch):
    from starlette.responses import Response

    from app.api.routes.market_sections import quotes as quotes_route
    from app.financial_data.market.quotes.national_team import (
        build_national_team_overview,
        build_support_backtest,
    )

    dates = ["2026-09-15", "2026-09-16"]
    members = ["510300", "510310", "510330", "159919"]
    full = build_national_team_response(
        share_history={code: {dates[0]: 100_000_000, dates[1]: 110_000_000} for code in members},
        etf_close_history={code: {dates[0]: 3.5, dates[1]: 3.6} for code in members},
        index_close_history={"csi300": {dates[0]: 3800.0, dates[1]: 3850.0}},
        fetched_at="2026-09-16T18:00:00+08:00",
        requested_days=30,
        expected_trading_dates=dates,
    )
    overview = build_national_team_overview(full)
    backtest = build_support_backtest(
        [
            {"date": f"2026-04-{index + 1:02d}", "status": "active", "confidence": 0.9, "coverage_ratio": 1.0, "csi300_close": 100.0 + index}
            for index in range(30)
        ]
    )

    async def fake_overview(days):
        return overview

    async def fake_backtest(days):
        return backtest

    monkeypatch.setattr(quotes_route, "get_national_team_overview_service", fake_overview)
    monkeypatch.setattr(quotes_route, "get_national_team_backtest_service", fake_backtest)

    overview_response = Response()
    assert asyncio.run(
        quotes_route.get_national_team_overview(_http_request(), overview_response, days=120)
    ) is overview
    overview_etag = overview_response.headers["etag"]
    assert overview_response.headers["cache-control"].startswith("private, max-age=")

    not_modified = asyncio.run(
        quotes_route.get_national_team_overview(
            _http_request([(b"if-none-match", overview_etag.encode())]),
            Response(),
            days=120,
        )
    )
    assert isinstance(not_modified, Response)
    assert not_modified.status_code == 304

    backtest_response = Response()
    assert asyncio.run(
        quotes_route.get_national_team_backtest(_http_request(), backtest_response, days=365)
    ) is backtest
    assert backtest_response.headers["etag"].startswith('"')
    assert backtest_response.headers["cache-control"] == "private, max-age=300"


def test_market_migration_15_creates_support_scores_table_on_upgrade():
    """旧库（迁移前已有基础表）升级时，迁移 15 必须补出评分表，且可重复执行。"""
    import sqlite3

    from app.infrastructure.persistence import ddl, migrations

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # 模拟迁移前的老库：除评分表以外的基础表都已存在。
    for statement in ddl.MARKET_TABLES:
        if "national_team_support_scores" in statement:
            continue
        conn.execute(statement)
    assert (
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='national_team_support_scores'"
        ).fetchone()
        is None
    )

    migrations.apply_migrations(conn, migrations.MARKET_MIGRATIONS)

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(national_team_support_scores)")}
    assert columns == {"date", "score", "status", "confidence", "coverage_ratio", "csi300_close", "updated_at"}
    assert conn.execute("SELECT 1 FROM schema_migrations WHERE version = 15").fetchone() is not None

    # 再跑一次不能报错，也不能重复插入迁移记录。
    migrations.apply_migrations(conn, migrations.MARKET_MIGRATIONS)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 15").fetchone()[0]
    assert count == 1


def test_backtest_cache_is_invalidated_after_scores_are_saved(monkeypatch):
    """评分落库后必须让回测缓存失效，否则新样本要等 5 分钟才生效。"""
    from app.core.cache import market_cache
    from app.financial_data.market.quotes import national_team as nt

    rows = [
        {
            "date": "2026-05-01",
            "score": 62.0,
            "status": "active",
            "confidence": 0.9,
            "coverage_ratio": 1.0,
            "csi300_close": 3800.0,
        }
    ]
    saved: list[list[dict]] = []

    async def fake_call_blocking(func, *, semaphore):  # noqa: ANN001
        return func()

    monkeypatch.setattr(nt, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(nt, "_support_score_rows", lambda response: rows)
    monkeypatch.setattr(nt.national_team_etf_store, "save_support_scores", lambda payload: saved.append(payload))

    cache_key = f"{nt._BACKTEST_CACHE_PREFIX}365"
    market_cache.set(cache_key, {"sentinel": True}, ttl=300)

    asyncio.run(nt._record_support_scores(object()))

    assert saved == [rows]
    assert market_cache.get(cache_key) is None


def test_backtest_cache_survives_persist_failure(monkeypatch):
    """落库失败时不能清缓存，否则每次请求都要重新算一遍回测。"""
    from app.core.cache import market_cache
    from app.financial_data.market.quotes import national_team as nt

    async def fake_call_blocking(func, *, semaphore):  # noqa: ANN001
        raise RuntimeError("db locked")

    monkeypatch.setattr(nt, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(nt, "_support_score_rows", lambda response: [{"date": "2026-05-01"}])

    cache_key = f"{nt._BACKTEST_CACHE_PREFIX}365"
    market_cache.set(cache_key, {"sentinel": True}, ttl=300)

    asyncio.run(nt._record_support_scores(object()))

    assert market_cache.get(cache_key) == {"sentinel": True}
