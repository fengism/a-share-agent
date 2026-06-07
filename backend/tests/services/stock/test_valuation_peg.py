import pandas as pd
import pytest

from app.models.stock import FinancialMetrics, InstitutionForecast, StockBasicInfo, StockConcept, ValuationFundamentals, ValuationProfile
from app.services.stock import valuation


def test_normalize_peg_growth_rate():
    """_normalize_peg_growth_rate converts percents, clamps extremes, and rejects invalid values."""
    assert valuation._normalize_peg_growth_rate(25) == 0.25
    assert valuation._normalize_peg_growth_rate(0.25) == 0.25
    assert valuation._normalize_peg_growth_rate(None) is None
    assert valuation._normalize_peg_growth_rate(-10) is None
    assert valuation._normalize_peg_growth_rate(0.02) is None
    assert valuation._normalize_peg_growth_rate(150) == 0.50


def test_parse_forecast_year():
    """_parse_forecast_year extracts a year from strings like '2026', '2026E', '2026年'."""
    assert valuation._parse_forecast_year("2026") == 2026
    assert valuation._parse_forecast_year("2026E") == 2026
    assert valuation._parse_forecast_year("2026年") == 2026
    assert valuation._parse_forecast_year("") is None
    assert valuation._parse_forecast_year("--") is None


def test_derive_peg_growth_rate_prefers_eps_forecast(monkeypatch):
    """_derive_peg_growth_rate prefers institution EPS forecasts with high confidence."""
    monkeypatch.setattr(valuation, "datetime", _FixedDateTime)
    forecasts = [
        InstitutionForecast(
            metric="EPS",
            year="2026E",
            institution_count=6,
            min_value=1.1,
            mean_value=1.25,
            max_value=1.4,
        )
    ]

    growth_rate, basis, confidence = valuation._derive_peg_growth_rate(
        forecasts,
        net_profit_ttm=1_000_000_000,
        total_shares=1_000_000_000,
        net_profit_yoy=10,
    )

    assert growth_rate == pytest.approx(0.25)
    assert "机构 EPS" in basis
    assert confidence == pytest.approx(0.72)


def test_derive_peg_growth_rate_falls_back_to_net_profit_yoy(monkeypatch):
    """_derive_peg_growth_rate falls back to historical net profit YoY growth when no forecasts exist."""
    monkeypatch.setattr(valuation, "datetime", _FixedDateTime)

    growth_rate, basis, confidence = valuation._derive_peg_growth_rate(
        [],
        net_profit_ttm=1_000_000_000,
        total_shares=1_000_000_000,
        net_profit_yoy=20,
    )

    assert growth_rate == 0.2
    assert "历史净利润同比" in basis
    assert confidence == 0.45


def test_derive_peg_growth_rate_penalizes_low_count_and_wide_range(monkeypatch):
    """_derive_peg_growth_rate reduces confidence when forecasts have few institutions or wide range."""
    monkeypatch.setattr(valuation, "datetime", _FixedDateTime)
    forecasts = [
        InstitutionForecast(
            metric="EPS",
            year="2026E",
            institution_count=1,
            min_value=0.6,
            mean_value=1.25,
            max_value=1.9,
        )
    ]

    growth_rate, _, confidence = valuation._derive_peg_growth_rate(
        forecasts,
        net_profit_ttm=1_000_000_000,
        total_shares=1_000_000_000,
        net_profit_yoy=None,
    )

    assert growth_rate == pytest.approx(0.25)
    assert confidence == pytest.approx(0.45)


def test_annualize_report_metric_by_report_period():
    """_annualize_report_metric scales a period metric up to a full year."""
    assert valuation._annualize_report_metric(100, "2026-12-31") == 100
    assert valuation._annualize_report_metric(100, "2026-06-30") == 200
    assert valuation._annualize_report_metric(100, "2026-03-31") == 400
    assert valuation._annualize_report_metric(100, "2026-09-30") == pytest.approx(100 * 4 / 3)


def test_build_peg_valuation_available():
    """_build_peg_valuation returns an available PEG valuation for a growth profile with positive growth."""
    profile = ValuationProfile(category="general", label="通用类", rationale=[])

    result = valuation._build_peg_valuation(
        net_profit_ttm=1_000_000_000,
        current_pe=30,
        peer_pe_median=25,
        growth_rate=0.25,
        growth_basis="历史净利润同比增长率 25.0%",
        current_price=20,
        total_shares=1_000_000_000,
        profile=profile,
        confidence_score=0.6,
    )

    assert result.available is True
    assert result.target_multiple == 25
    assert result.per_share_value == 25
    assert "目标 PEG" in result.basis


def test_build_peg_valuation_unavailable_for_low_growth():
    """_build_peg_valuation returns an unavailable result when growth is too low or missing."""
    profile = ValuationProfile(category="general", label="通用类", rationale=[])

    result = valuation._build_peg_valuation(
        net_profit_ttm=1_000_000_000,
        current_pe=30,
        peer_pe_median=25,
        growth_rate=None,
        growth_basis=None,
        current_price=20,
        total_shares=1_000_000_000,
        profile=profile,
        confidence_score=0.3,
    )

    assert result.available is False
    assert result.reason == "成长率过低或不可用"


def test_build_peg_valuation_caps_target_pe():
    """_build_peg_valuation caps the target PE to the peer median."""
    profile = ValuationProfile(category="growth", label="成长类", rationale=[])

    result = valuation._build_peg_valuation(
        net_profit_ttm=1_000_000_000,
        current_pe=100,
        peer_pe_median=20,
        growth_rate=0.5,
        growth_basis="历史净利润同比增长率 50.0%",
        current_price=20,
        total_shares=1_000_000_000,
        profile=profile,
        confidence_score=0.6,
    )

    assert result.available is True
    assert result.target_multiple == 30
    assert "同行 PE 中位数" in result.basis


@pytest.mark.asyncio
async def test_get_valuation_detail_annualizes_profit_fallback_for_semiannual_report(monkeypatch):
    """get_valuation_detail annualises a semi-annual report when computing PE/PS fair values."""
    async def fake_basic_info(code: str):
        return StockBasicInfo(
            code=code,
            name="测试股份",
            total_shares=1_000_000_000,
            market_cap=30_000_000_000,
            first_industry=StockConcept(code="", name="软件"),
        )

    async def fake_valuation(code: str):
        return {
            "code": code,
            "pe_ttm": None,
            "pb": 3.0,
            "ps_ttm": None,
            "peers": [{"name": "同行A", "code": "000001", "pe_ttm": 1.0, "pb": 2.5, "ps_ttm": 1.0}],
        }

    async def fake_financial_metrics(code: str):
        return FinancialMetrics(
            code=code,
            latest_report_date="2026-06-30",
            metrics={
                "营收": 5_000_000_000,
                "营收同比": 15.0,
                "净利润": 500_000_000,
                "净利润同比": 20.0,
                "扣非净利润": 450_000_000,
                "扣非净利润同比": 18.0,
                "股东权益": 8_000_000_000,
                "经营现金流": 400_000_000,
            },
        )

    async def fake_call_blocking(func, *args, **kwargs):
        return pd.DataFrame()

    async def fake_percentile(*args, **kwargs):
        return None

    monkeypatch.setattr(valuation, "get_basic_info", fake_basic_info)
    monkeypatch.setattr(valuation, "get_valuation", fake_valuation)
    monkeypatch.setattr(valuation, "get_financial_metrics", fake_financial_metrics)
    monkeypatch.setattr(valuation, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(valuation.cache, "get", lambda key: None)
    monkeypatch.setattr(valuation.cache, "set", lambda *args, **kwargs: None)

    detail = await valuation.get_valuation_detail("600519", fake_percentile)

    assert detail.fair_values["pe"].equity_value == 1_000_000_000
    assert detail.fair_values["ps"].equity_value == 10_000_000_000
    assert detail.fair_values["dcf"].base_cashflow == 560_000_000


@pytest.mark.asyncio
async def test_get_valuation_detail_includes_peg(monkeypatch):
    """get_valuation_detail includes a PEG method and institution forecasts in the result."""
    async def fake_basic_info(code: str):
        return StockBasicInfo(
            code=code,
            name="测试股份",
            total_shares=1_000_000_000,
            market_cap=30_000_000_000,
            first_industry=StockConcept(code="", name="软件"),
        )

    async def fake_valuation(code: str):
        return {
            "code": code,
            "pe_ttm": 30.0,
            "pb": 3.0,
            "ps_ttm": 5.0,
            "peers": [{"name": "同行A", "code": "000001", "pe_ttm": 25.0, "pb": 2.5, "ps_ttm": 4.0}],
        }

    async def fake_financial_metrics(code: str):
        return FinancialMetrics(
            code=code,
            latest_report_date="2026-03-31",
            metrics={
                "营收": 10_000_000_000,
                "营收同比": 15.0,
                "净利润": 1_000_000_000,
                "净利润同比": 20.0,
                "扣非净利润": 900_000_000,
                "扣非净利润同比": 18.0,
                "股东权益": 8_000_000_000,
                "经营现金流": 800_000_000,
            },
        )

    async def fake_call_blocking(func, *args, **kwargs):
        return pd.DataFrame([
            {"指标": "EPS", "年度": "2026E", "预测机构数": 6, "最小值": 1.1, "均值": 1.25, "最大值": 1.4, "行业平均数": 1.2, "单位": "元"}
        ])

    async def fake_percentile(*args, **kwargs):
        return 50.0

    monkeypatch.setattr(valuation, "get_basic_info", fake_basic_info)
    monkeypatch.setattr(valuation, "get_valuation", fake_valuation)
    monkeypatch.setattr(valuation, "get_financial_metrics", fake_financial_metrics)
    monkeypatch.setattr(valuation, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(valuation.cache, "get", lambda key: None)
    monkeypatch.setattr(valuation.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(valuation, "datetime", _FixedDateTime)

    detail = await valuation.get_valuation_detail("600519", fake_percentile)

    assert detail.multiples.peg == pytest.approx(1.2)
    assert detail.fair_values["peg"].available is True
    assert "peg" in detail.method_weights
    assert detail.institution_forecasts[0].metric == "EPS"


class _FixedDateTime:
    @staticmethod
    def now():
        """Return a fixed datetime stand-in for valuation tests.

        Return:
            a _FixedNow instance representing year 2026.
        """
        return _FixedNow(2026)


class _FixedNow:
    def __init__(self, year: int):
        """Store the fixed year on the stand-in datetime.

        Param:
            year: the fixed year to expose via the .year attribute.
        Return:
            None
        """
        self.year = year
