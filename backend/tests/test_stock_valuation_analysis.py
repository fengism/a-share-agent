"""个股估值分析的质量调整、分歧控制与数据定位测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from app.financial_data.stock.profile.schemas import StockBasicInfo
from app.financial_data.stock.valuation.blending import (
    _adjust_method_weights,
    _base_method_weights,
    _build_blended_range,
    _build_valuation_view,
    _consensus_penalty,
    _method_dispersion,
)
from app.financial_data.stock.valuation.detail import (
    _build_multiple_method_contexts,
    _build_peer_summary,
    _build_weighted_outputs,
    _resolve_price_and_shares,
)
from app.financial_data.stock.valuation.helpers import (
    _annual_metric_average,
    _cap_target_multiple,
    _derive_ttm_report_metric,
    _normalize_peg_growth_rate,
    _normalized_metric_basis,
    _peer_quality_benchmark,
    _quality_adjusted_multiple,
)
from app.financial_data.stock.valuation.methods import (
    _build_dcf_valuation,
    _build_multiple_valuation,
    _build_peg_valuation,
)
from app.financial_data.stock.valuation.orchestrator import _parse_valuation_comparison
from app.financial_data.stock.valuation.profile import (
    _calc_net_margin,
    _calc_roe,
    _classify_stock_profile,
)
from app.financial_data.stock.valuation.schemas import (
    StockValuation,
    ValuationFundamentals,
    ValuationMethodResult,
    ValuationPeer,
    ValuationPercentiles,
    ValuationProfile,
)


def _moutai_like_peers() -> list[ValuationPeer]:
    peers = [
        ValuationPeer(name="金徽酒", code="603919", pe_ttm=32.3882, pb=2.5721, ps_ttm=2.9416),
        ValuationPeer(name="五粮液", code="000858", pe_ttm=21.3819, pb=2.3611, ps_ttm=6.1571),
        ValuationPeer(name="迎驾贡酒", code="603198", pe_ttm=15.8638, pb=3.0197, ps_ttm=5.1004),
        ValuationPeer(name="老白干酒", code="600559", pe_ttm=27.1561, pb=1.8478, ps_ttm=2.6879),
        ValuationPeer(name="今世缘", code="603369", pe_ttm=15.0428, pb=2.1551, ps_ttm=3.8229),
    ]
    forward_pes = [29.1443, 18.4112, 15.3335, 22.7961, 14.2364]
    for peer, forward_pe in zip(peers, forward_pes):
        peer._pe_forward = forward_pe
    return peers


def _method_result(
    method: str,
    value: float,
    *,
    confidence: float = 0.8,
    quality: float = 0.9,
    value_range: list[float] | None = None,
) -> ValuationMethodResult:
    return ValuationMethodResult(
        method=method,
        available=True,
        per_share_value=value,
        confidence_score=confidence,
        data_quality_score=quality,
        value_range=value_range if value_range is not None else [round(value * 0.8, 2), round(value * 1.2, 2)],
    )


def test_multiple_valuation_prefers_relative_rerating_to_avoid_mixed_basis() -> None:
    """当前倍数可用时，应按目标/当前倍数重估，避免财务口径错配。"""
    relative = _build_multiple_valuation(
        "PE",
        basis_metric=50.0,
        target_multiple=30.0,
        current_price=10.0,
        total_shares=100.0,
        basis="同行 PE 中位数",
        confidence_score=0.7,
        applicability="测试",
        current_multiple=10.0,
    )
    fallback = _build_multiple_valuation(
        "PE",
        basis_metric=50.0,
        target_multiple=30.0,
        current_price=10.0,
        total_shares=100.0,
        basis="同行 PE 中位数",
        confidence_score=0.7,
        applicability="测试",
    )

    assert relative.per_share_value == 30.0
    assert relative.equity_value == 3000.0
    assert "相对重估" in (relative.basis or "")
    assert fallback.per_share_value == 15.0


def test_single_method_does_not_form_blended_conclusion() -> None:
    """只有一个可用方法时不能把它当成“综合估值”。"""
    fair_values = {"dcf": _method_result("DCF", 284.0)}

    weights = _adjust_method_weights(
        fair_values,
        _base_method_weights(ValuationProfile(category="financial", label="金融类")),
    )

    assert weights == {}


def test_financial_profile_disables_dcf_and_peg() -> None:
    """金融企业现金流口径不适用 FCFE，PEG 也不是主要定价工具。"""
    profile = ValuationProfile(category="financial", label="金融类")

    dcf = _build_dcf_valuation(
        1_000_000_000.0,
        100_000_000.0,
        5.0,
        5.0,
        42.0,
        100_000_000.0,
        disabled_reason="金融企业现金流口径与 FCFE 不匹配",
    )
    peg = _build_peg_valuation(
        100_000_000.0,
        7.0,
        6.0,
        0.10,
        "历史增速",
        42.0,
        100_000_000.0,
        profile,
        0.5,
    )

    assert dcf.available is False
    assert peg.available is False


def test_cyclical_profile_disables_dcf_and_peg() -> None:
    """周期行业当期现金流与增速都不稳定，不应让 DCF/PEG 主导估值。"""
    profile = ValuationProfile(category="cyclical", label="周期类")

    dcf = _build_dcf_valuation(
        1_000_000_000.0,
        100_000_000.0,
        5.0,
        5.0,
        42.0,
        100_000_000.0,
        disabled_reason="周期行业当期现金流受商品价格影响大",
    )
    peg = _build_peg_valuation(
        100_000_000.0,
        7.0,
        6.0,
        0.10,
        "历史增速",
        42.0,
        100_000_000.0,
        profile,
        0.5,
    )

    assert dcf.available is False
    assert peg.available is False


def test_valuation_comparison_provider_falls_back_when_akshare_column_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """银行股缺少 EV/EBITDA 时，应回退到东财原始响应而不是让整段估值缺失。"""
    from app.infrastructure.providers.akshare import financials

    def raise_missing_column(symbol: str):
        raise KeyError("['EV/EBITDA-24A'] not in index")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "result": {
                    "data": [
                        {
                            "CORRE_SECURITY_CODE": "600036",
                            "CORRE_SECURITY_NAME": "招商银行",
                            "PE_TTM": 7.05,
                            "PE_1Y": 6.93,
                            "PB_MRQ": 0.93,
                            "PS_TTM": 3.09,
                        }
                    ]
                }
            }

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(financials.ak, "stock_zh_valuation_comparison_em", raise_missing_column)
    monkeypatch.setattr(financials, "get_provider_session", lambda: FakeSession())

    frame = financials.fetch_stock_valuation_comparison("SH600036")

    assert list(frame.columns) == ["代码", "简称", "市盈率-TTM", "市盈率-25E", "市净率-MRQ", "市销率-TTM"]
    assert frame.iloc[0]["代码"] == "600036"


def test_classify_stock_profile_uses_ttm_profit_for_loss_detection() -> None:
    """报告期盈利但 TTM 亏损时，应识别为亏损画像。"""
    info = StockBasicInfo(code="688180", name="君实生物")
    fundamentals = ValuationFundamentals(net_profit=100.0, non_net_profit=50.0)

    assert _classify_stock_profile(info, fundamentals).category != "loss_making"
    assert _classify_stock_profile(info, fundamentals, net_profit_ttm=-10.0).category == "loss_making"


def test_ttm_yoy_bridge_uses_yoy_when_prior_comparable_missing() -> None:
    """上年同期缺失时，用本期同比反推上年同期，避免简单年化造成季节性失真。"""
    rows = [
        {"REPORT_DATE": "2025-12-31", "PARENT_NETPROFIT": 100.0},
        {"REPORT_DATE": "2026-06-30", "PARENT_NETPROFIT": 60.0},
    ]

    ttm, source = _derive_ttm_report_metric(
        rows,
        ("PARENT_NETPROFIT",),
        "2026-06-30",
        yoy=20.0,
    )

    assert ttm == pytest.approx(110.0)
    assert source == "reported_ttm_yoy_bridge"


def test_peg_growth_requires_meaningful_growth() -> None:
    """低增速公司不应硬套 PEG，否则会把稳定公司估成极低价值。"""
    assert _normalize_peg_growth_rate(0.05) is None
    assert _normalize_peg_growth_rate(0.10) == pytest.approx(0.10)


def test_annual_metric_average_normalizes_cyclical_profit() -> None:
    """近三年平均盈利用于周期股正常化，避免峰值利润直接外推。"""
    rows = [
        {"REPORT_DATE": "2022-12-31", "PARENT_NETPROFIT": 80.0},
        {"REPORT_DATE": "2023-12-31", "PARENT_NETPROFIT": 100.0},
        {"REPORT_DATE": "2024-12-31", "PARENT_NETPROFIT": 120.0},
    ]

    assert _annual_metric_average(rows, ("PARENT_NETPROFIT",), 3) == pytest.approx(100.0)


def test_cyclical_context_uses_normalized_roe_and_margin() -> None:
    """周期股 PB/PS 质量调整应使用近三年平均盈利，而不是峰值 TTM。"""
    valuation = StockValuation(
        code="601088",
        pe_ttm=20.0,
        pb=2.4,
        ps_ttm=3.5,
        peers=_moutai_like_peers(),
    )
    peer_summary = _build_peer_summary(valuation)
    profile = ValuationProfile(category="cyclical", label="周期类")

    without_normalized = _build_multiple_method_contexts(
        valuation,
        ValuationPercentiles(),
        peer_summary,
        profile,
        stock_roe=0.30,
        stock_net_margin=0.30,
    )
    with_normalized = _build_multiple_method_contexts(
        valuation,
        ValuationPercentiles(),
        peer_summary,
        profile,
        stock_roe=0.30,
        stock_net_margin=0.30,
        normalized_roe=0.10,
        normalized_net_margin=0.12,
        normalized_basis="近三年平均",
    )

    assert without_normalized["pb"].target is not None
    assert with_normalized["pb"].target is not None
    assert with_normalized["pb"].target < without_normalized["pb"].target
    assert with_normalized["pb"].basis is not None and "正常化" in with_normalized["pb"].basis
    assert with_normalized["ps"].basis is not None and "正常化" in with_normalized["ps"].basis


def test_normalized_metric_basis_falls_back_to_annual_ttm_average() -> None:
    """历史年报不足两年时，用最近年报与 TTM 两点平滑。"""
    rows = [{"REPORT_DATE": "2025-12-31", "PARENT_NETPROFIT": 100.0}]

    value, basis = _normalized_metric_basis(rows, ("PARENT_NETPROFIT",), ttm_value=80.0)

    assert value == pytest.approx(90.0)
    assert basis == "近一年与 TTM 平均"


def test_parse_valuation_comparison_matches_target_row_and_drops_aggregates() -> None:
    """东财表首行是末位同行，必须按代码取目标行并剔除行业汇总行。"""
    frame = pd.DataFrame(
        [
            {"代码": "603919", "简称": "金徽酒", "市盈率-TTM": 30.0, "市盈率-25E": 25.0, "市净率-MRQ": 2.4, "市销率-TTM": 2.8},
            {"代码": None, "简称": "行业平均", "市盈率-TTM": 43.0, "市盈率-25E": 40.0, "市净率-MRQ": 2.9, "市销率-TTM": 5.2},
            {"代码": None, "简称": "行业中值", "市盈率-TTM": 18.0, "市盈率-25E": 16.0, "市净率-MRQ": 2.2, "市销率-TTM": 3.8},
            {"代码": "600519", "简称": "贵州茅台", "市盈率-TTM": 20.4, "市盈率-25E": 19.7, "市净率-MRQ": 6.6, "市销率-TTM": 9.6},
            {"代码": "000858", "简称": "五粮液", "市盈率-TTM": 21.4, "市盈率-25E": 18.4, "市净率-MRQ": 2.36, "市销率-TTM": 6.16},
        ]
    )

    pe_ttm, pb, ps_ttm, pe_forward, peers = _parse_valuation_comparison(frame, "600519")

    assert (pe_ttm, pb, ps_ttm, pe_forward) == (20.4, 6.6, 9.6, 19.7)
    assert [peer.code for peer in peers] == ["603919", "000858"]
    assert peers[0]._pe_forward == 25.0
    assert peers[1]._pe_forward == 18.4


def test_parse_valuation_comparison_without_target_falls_back_to_basic_info() -> None:
    """目标行缺失时不得拿同行倍数冒充自身倍数。"""
    frame = pd.DataFrame(
        [
            {"代码": "603919", "简称": "金徽酒", "市盈率-TTM": 30.0, "市盈率-25E": 25.0, "市净率-MRQ": 2.4, "市销率-TTM": 2.8},
            {"代码": None, "简称": "行业中值", "市盈率-TTM": 18.0, "市盈率-25E": 16.0, "市净率-MRQ": 2.2, "市销率-TTM": 3.8},
        ]
    )

    pe_ttm, pb, ps_ttm, pe_forward, peers = _parse_valuation_comparison(frame, "600519")

    assert pe_ttm is None
    assert pb is None
    assert ps_ttm is None
    assert pe_forward is None
    assert [peer.code for peer in peers] == ["603919"]


def test_quality_adjusted_multiple_scales_and_caps_by_fundamental_quality() -> None:
    """高 ROE 公司应获得更高 PB，极端差异要截断。"""
    adjusted, note = _quality_adjusted_multiple(2.0, 0.30, 0.10, label="ROE")

    assert adjusted == 5.0
    assert note is not None and "截断" in note

    discounted, _ = _quality_adjusted_multiple(2.0, 0.05, 0.10, label="ROE")
    assert discounted == 1.0

    unchanged, unchanged_note = _quality_adjusted_multiple(None, 0.30, 0.10, label="ROE")
    assert unchanged is None and unchanged_note is None

    depressed, depressed_note = _quality_adjusted_multiple(0.635, 0.049, 0.0176, label="ROE")
    assert depressed == 0.635
    assert depressed_note is not None and "过低" in depressed_note


def test_peer_quality_benchmark_uses_upper_quartile_for_leaders() -> None:
    """行业龙头应对比同行上四分位，而不是被同行中位数推到现价数倍。"""
    peers = _moutai_like_peers()

    benchmark, basis = _peer_quality_benchmark(peers, "pb", "pe_ttm", target_metric=0.3544)
    low_benchmark, low_basis = _peer_quality_benchmark(peers, "pb", "pe_ttm", target_metric=0.03)

    assert benchmark is not None and low_benchmark is not None
    assert benchmark > low_benchmark
    assert basis == "同行上四分位"
    assert low_basis == "同行中位数"


def test_cap_target_multiple_limits_peer_multiple_blowups() -> None:
    """同行盈利失真导致目标倍数远高于当前倍数时，应设置上限。"""
    capped, note = _cap_target_multiple(123.5, 13.1, label="PE")
    unchanged, unchanged_note = _cap_target_multiple(18.0, 13.1, label="PE")

    assert capped == pytest.approx(19.65)
    assert note is not None and "约束" in note
    assert unchanged == 18.0
    assert unchanged_note is None


def test_forward_pe_switches_when_peer_ttm_earnings_are_depressed() -> None:
    """同行 TTM PE 远高于前瞻 PE 时，应改用前瞻口径，避免盈利低谷放大估值。"""
    peers = [
        ValuationPeer(name=f"同行{i}", code=f"00000{i}", pe_ttm=ttm, pb=1.0, ps_ttm=1.0)
        for i, ttm in enumerate([60.0, 70.0, 50.0, 80.0, 65.0], start=1)
    ]
    for peer, forward in zip(peers, [12.0, 13.0, 11.0, 14.0, 12.0]):
        peer._pe_forward = forward
    valuation = StockValuation(code="601088", pe_ttm=20.0, pb=2.4, ps_ttm=3.5, peers=peers)
    valuation._pe_forward = 15.0
    peer_summary = _build_peer_summary(valuation)

    contexts = _build_multiple_method_contexts(
        valuation,
        ValuationPercentiles(),
        peer_summary,
        ValuationProfile(category="cyclical", label="周期类"),
        stock_roe=0.12,
        stock_net_margin=0.18,
    )

    assert contexts["pe"].target == pytest.approx(12.0)
    assert contexts["pe"].current_multiple == pytest.approx(15.0)
    assert contexts["pe"].basis is not None and "前瞻" in contexts["pe"].basis


def test_forward_pe_not_used_when_ttm_and_forward_are_close() -> None:
    """TTM 与前瞻 PE 接近时保持 TTM 口径，避免无谓切换。"""
    valuation = StockValuation(code="600519", pe_ttm=20.4, pb=6.61, ps_ttm=9.59, peers=_moutai_like_peers())
    valuation._pe_forward = 19.75
    peer_summary = _build_peer_summary(valuation)

    contexts = _build_multiple_method_contexts(
        valuation,
        ValuationPercentiles(),
        peer_summary,
        ValuationProfile(category="stable", label="稳定经营类"),
        stock_roe=0.35,
        stock_net_margin=0.48,
    )

    assert contexts["pe"].current_multiple is None
    assert contexts["pe"].basis is not None and "前瞻" not in contexts["pe"].basis


def test_multiple_method_contexts_adjust_pb_and_ps_for_profitability() -> None:
    """高 ROE、高净利率公司的 PB/PS 目标倍数应高于同行中位数。"""
    valuation = StockValuation(
        code="600519",
        pe_ttm=20.4,
        pb=6.61,
        ps_ttm=9.59,
        peers=_moutai_like_peers(),
    )
    peer_summary = _build_peer_summary(valuation)
    profile = ValuationProfile(category="stable", label="稳定经营类")

    contexts = _build_multiple_method_contexts(
        valuation,
        ValuationPercentiles(),
        peer_summary,
        profile,
        stock_roe=0.3544,
        stock_net_margin=0.4824,
    )

    assert peer_summary.pb_median is not None
    assert peer_summary.ps_median is not None
    assert contexts["pb"].target is not None and contexts["pb"].target > peer_summary.pb_median
    assert contexts["ps"].target is not None and contexts["ps"].target > peer_summary.ps_median
    assert contexts["pb"].basis is not None and "质量调整" in contexts["pb"].basis
    assert contexts["ps"].basis is not None and "质量调整" in contexts["ps"].basis


def test_multiple_method_contexts_disables_ps_for_financials() -> None:
    """金融企业收入口径不可比，PS 不应参与综合估值。"""
    valuation = StockValuation(code="600036", pe_ttm=6.0, pb=1.0, ps_ttm=2.0, peers=_moutai_like_peers())
    peer_summary = _build_peer_summary(valuation)
    profile = ValuationProfile(category="financial", label="金融类")

    contexts = _build_multiple_method_contexts(
        valuation,
        ValuationPercentiles(),
        peer_summary,
        profile,
        stock_roe=0.12,
        stock_net_margin=0.30,
    )

    assert contexts["ps"].target is None
    assert contexts["ps"].confidence <= 0.2


def test_consensus_penalty_downweights_methods_far_from_median() -> None:
    """偏离共识 1.5 倍以上应连续降权，而不是到 2 倍才一次性降权。"""
    assert _consensus_penalty(1200.0, 1200.0) == 1.0
    assert _consensus_penalty(1800.0, 1200.0) == 1.0
    assert _consensus_penalty(2400.0, 1200.0) < 0.6
    assert _consensus_penalty(400.0, 1200.0) < 0.3


def test_weighted_outputs_keep_range_around_method_dispersion() -> None:
    """综合区间不能被加权平均压得比方法分歧还窄。"""
    fair_values = {
        "pe": _method_result("PE", 1500.0),
        "pb": _method_result("PB", 1180.0),
        "ps": _method_result("PS", 1080.0),
        "dcf": _method_result("DCF", 1300.0),
    }
    profile = ValuationProfile(category="stable", label="稳定经营类")

    outputs = _build_weighted_outputs(fair_values, profile, current_price=1274.0)

    assert outputs.blended_fair_value is not None
    assert outputs.fair_value_range is not None
    assert outputs.fair_value_range[0] <= outputs.blended_fair_value <= outputs.fair_value_range[1]
    assert outputs.method_dispersion is not None and outputs.method_dispersion < 1.5
    assert outputs.valuation_view == "基本合理"


def test_loss_making_profile_uses_limited_reference_view() -> None:
    """亏损公司缺少盈利锚，不应给出过于确定的高估/低估结论。"""
    fair_values = {
        "pb": _method_result("PB", 8.0),
        "ps": _method_result("PS", 9.0),
    }

    outputs = _build_weighted_outputs(
        fair_values,
        ValuationProfile(category="loss_making", label="亏损/利润承压类"),
        current_price=30.0,
    )

    assert outputs.valuation_view == "参考性有限"
    assert outputs.valuation_summary is not None and "研发管线" in outputs.valuation_summary


def test_large_method_dispersion_is_reported_instead_of_hiding_it() -> None:
    """有效方法结果差 2 倍以上时应标注分歧较大，而不是给出“基本合理”。"""
    fair_values = {
        "pe": _method_result("PE", 1500.0),
        "pb": _method_result("PB", 600.0),
        "ps": _method_result("PS", 1400.0),
        "dcf": _method_result("DCF", 1300.0),
    }
    weights = _adjust_method_weights(fair_values, _base_method_weights(ValuationProfile(category="stable", label="稳定经营类")))

    dispersion = _method_dispersion(fair_values, weights)
    view = _build_valuation_view([500.0, 1500.0], 1200.0, 1200.0, dispersion)

    assert weights["pb"] >= 0.05
    assert dispersion is not None and dispersion > 2.2
    assert view == "分歧较大"


def test_blended_range_ignores_methods_without_range_and_uses_quartiles() -> None:
    """个别方法缺区间时不应让整个综合区间变为空。"""
    fair_values = {
        "pe": _method_result("PE", 1500.0, value_range=[1200.0, 1800.0]),
        "pb": _method_result("PB", 1100.0, value_range=None),
        "ps": _method_result("PS", 900.0, value_range=[800.0, 1000.0]),
    }
    fair_values["pb"].value_range = None
    weights = {"pe": 0.6, "pb": 0.3, "ps": 0.1}

    blended_range = _build_blended_range(fair_values, weights)

    assert blended_range is not None
    assert blended_range[0] <= 1100.0
    assert blended_range[1] >= 1500.0


def test_resolve_price_and_shares_prefers_quote_price_and_derives_missing_shares() -> None:
    """股本缺失时用行情现价补齐；市值与股本同时可用时优先保持口径一致。"""
    info = StockBasicInfo(
        code="600519",
        name="贵州茅台",
        current_price=1700.0,
        market_cap=2_000_000_000_000.0,
        total_shares=None,
    )

    price, shares = _resolve_price_and_shares(info)

    assert price == 1700.0
    assert shares == pytest.approx(2_000_000_000_000.0 / 1700.0)

    consistent = StockBasicInfo(
        code="600519",
        name="贵州茅台",
        current_price=1700.0,
        market_cap=2_000_000_000_000.0,
        total_shares=1_250_000_000.0,
    )
    derived_price, derived_shares = _resolve_price_and_shares(consistent)
    assert derived_price == pytest.approx(1600.0)
    assert derived_shares == pytest.approx(1_250_000_000.0)


def test_calc_roe_and_net_margin_use_ttm_profit() -> None:
    """ROE/净利率应支持传入 TTM 净利润，避免用报告期利润低估盈利能力。"""
    fundamentals = ValuationFundamentals(
        net_profit=10.0,
        revenue=100.0,
        shareholders_equity=100.0,
    )

    assert _calc_roe(fundamentals, net_profit=20.0) == pytest.approx(0.2)
    assert _calc_net_margin(20.0, 100.0) == pytest.approx(0.2)
    assert _calc_net_margin(20.0, None) is None
