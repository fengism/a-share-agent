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
