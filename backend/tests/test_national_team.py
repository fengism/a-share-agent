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

