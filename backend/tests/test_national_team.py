import asyncio
import time
from datetime import datetime

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

    response = build_national_team_response(
        share_history=share_history,
        etf_close_history=etf_close_history,
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
    assert flow_pt.flows_by_index.get("沪深300") == pytest.approx(0.72)
    assert flow_pt.flows_by_index.get("中证A500") == pytest.approx(0.1)
    assert flow_pt.flows_by_category.get("core_broad") == pytest.approx(0.72)
    assert flow_pt.flows_by_category.get("a500") == pytest.approx(0.1)


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

    async def fake_service(days, *, include_etf_points=True):
        seen.append(include_etf_points)
        return payload

    monkeypatch.setattr(quotes_route, "get_national_team_etf_holdings_service", fake_service)

    response = Response()
    result = asyncio.run(
        quotes_route.get_national_team_etf_holdings(
            _http_request(), response, days=120, include_etf_points=False
        )
    )
    assert result is payload
    assert seen == [False]
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')
    assert response.headers["cache-control"].startswith("private, max-age=")

    not_modified = asyncio.run(
        quotes_route.get_national_team_etf_holdings(
            _http_request([(b"if-none-match", etag.encode())]),
            Response(),
            days=120,
            include_etf_points=False,
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
