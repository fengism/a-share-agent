"""PDF 报告章节渲染器测试。

这些章节原先内联在 750 行的 `generate_research_report_html` 里、无法单独验证；
拆出后固定住「空输入返回空串」与关键内容渲染行为。
"""

from __future__ import annotations

from app.modules.analysis.models import (
    BusinessModelResearch,
    DataGap,
    InversionAnalysis,
    MoatAssessment,
    MoatItem,
    RiskCase,
    SegmentQuality,
    ValuationScenario,
    ValuationScenarios,
)
from app.modules.analysis.pdf_service import (
    _render_data_gaps,
    _render_moats,
    _render_risks,
    _render_segment_quality,
    _render_valuation_scenarios,
)


def test_segment_quality_renders_cards_and_handles_empty() -> None:
    assert _render_segment_quality(None) == ""
    assert _render_segment_quality(BusinessModelResearch()) == ""

    html = _render_segment_quality(BusinessModelResearch(segment_quality=[
        SegmentQuality(segment="茅台酒", role="核心", growth_quality="稳健", evidence_confidence=0.8),
    ]))
    assert "茅台酒" in html
    assert "80% 证据" in html
    assert "增长质量" in html


def test_moats_render_evidence_and_counterevidence() -> None:
    assert _render_moats(None) == ""
    assert _render_moats(MoatAssessment()) == ""

    html = _render_moats(MoatAssessment(moats=[
        MoatItem(
            moat_type="brand_pricing",
            evidence=["提价能力强"],
            counterevidence=["年轻化不足"],
            strength="strong",
            direction="stable",
        ),
    ]))
    assert "品牌与定价权" in html
    assert "提价能力强" in html
    assert "年轻化不足" in html
    assert "强度: 强" in html


def test_risks_prefer_structured_risks_then_fall_back_to_warnings() -> None:
    assert _render_risks(None, None) == ""

    fallback = _render_risks(None, ["海外宏观波动"])
    assert "海外宏观波动" in fallback

    structured = _render_risks(
        InversionAnalysis(risks=[RiskCase(risk="需求下滑", failure_path="动销转弱", leading_indicators=["批价"])]),
        ["不应出现"],
    )
    assert "需求下滑" in structured
    assert "动销转弱" in structured
    assert "批价" in structured
    assert "不应出现" not in structured


def test_valuation_scenarios_requires_all_three_and_formats_ranges() -> None:
    assert _render_valuation_scenarios(None, "¥") == ""

    scenarios = ValuationScenarios(
        bull=ValuationScenario(scenario="bull", fair_value_range=(1800.0, 2000.0)),
        base=ValuationScenario(scenario="base", fair_value_range=(1500.0, 1700.0)),
        bear=ValuationScenario(scenario="bear", fair_value_range=(1000.0, 1200.0)),
    )
    html = _render_valuation_scenarios(scenarios, "HK$")
    assert "HK$1800.00 - HK$2000.00" in html
    assert "乐观情景 (Bull)" in html
    assert "悲观情景 (Bear)" in html


def test_data_gaps_render_and_handle_empty() -> None:
    assert _render_data_gaps([]) == ""

    html = _render_data_gaps([DataGap(topic="季度分部数据", missing_data="缺拆分", decision_impact="影响增速判断")])
    assert "09 · 数据缺口与待核验清单" in html
    assert "季度分部数据" in html
    assert "影响增速判断" in html
