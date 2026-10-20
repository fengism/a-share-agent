"""结构化意见解析与分歧分类。

`classify_disagreement` 的 `risk_veto` 分支此前**零覆盖**，而它是唯一一条「硬性否决」
——风险维度判高风险看空时，综合结论不得买入。这条错了不是文案问题，是给出错误建议。
"""

from __future__ import annotations

import pytest

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.orchestration.opinions import (
    AgentOpinion,
    _clamp01,
    build_synthesis_guidance,
    classify_disagreement,
    parse_opinion_block,
)


def _opinion(agent: str = "technical", signal: str = "bullish",
             confidence: float = 0.7, risk: str = "none") -> AgentOpinion:
    return AgentOpinion(
        agent_name=agent, display_name=f"{agent}维度",
        signal=signal, confidence=confidence, risk_level=risk,  # type: ignore[arg-type]
    )


# --- 解析 ------------------------------------------------------------------


def test_standard_block_is_removed_and_parsed():
    analysis = '分析正文。\n\n```agent-opinion\n{"signal":"bearish","confidence":0.8,"risk_level":"high"}\n```'
    cleaned, opinion = parse_opinion_block("risk", "风险维度", analysis)

    assert cleaned == "分析正文。"
    assert opinion is not None
    assert (opinion.signal, opinion.risk_level, opinion.confidence) == ("bearish", "high", 0.8)


def test_bare_json_block_at_the_end_is_accepted():
    analysis = '正文。\n```json\n{"signal":"bullish"}\n```'
    _, opinion = parse_opinion_block("technical", "技术维度", analysis)
    assert opinion is not None and opinion.signal == "bullish"


def test_bare_json_in_the_middle_is_not_treated_as_an_opinion():
    """无显式标记的 JSON 只接受末尾独立结论，否则普通数据会被当成意见。"""
    analysis = '```json\n{"signal":"bullish"}\n```\n后面还有正文。'
    cleaned, opinion = parse_opinion_block("technical", "技术维度", analysis)

    assert opinion is None
    assert cleaned == analysis


def test_unfenced_json_at_the_end_is_accepted():
    analysis = '正文。\n{"signal":"neutral","confidence":0.5}'
    cleaned, opinion = parse_opinion_block("macro", "宏观维度", analysis)

    assert cleaned == "正文。"
    assert opinion is not None and opinion.signal == "neutral"


def test_invalid_signal_is_rejected_and_text_kept():
    analysis = '正文。\n```agent-opinion\n{"signal":"strong_buy"}\n```'
    cleaned, opinion = parse_opinion_block("technical", "技术维度", analysis)

    assert opinion is None
    assert "strong_buy" in cleaned, "无效块原样保留，不能吞掉正文"


def test_unknown_risk_level_falls_back_to_none():
    _, opinion = parse_opinion_block(
        "risk", "风险维度", '```agent-opinion\n{"signal":"bearish","risk_level":"catastrophic"}\n```',
    )
    assert opinion is not None and opinion.risk_level == "none"


def test_broken_json_and_unclosed_fence_are_ignored():
    for analysis in ('正文。\n```agent-opinion\n{not json}\n```', '正文。\n```agent-opinion\n{"signal":"bullish"}',):
        cleaned, opinion = parse_opinion_block("technical", "技术维度", analysis)
        assert opinion is None
        assert cleaned == analysis


def test_the_last_valid_candidate_wins():
    analysis = (
        '```agent-opinion\n{"signal":"bullish"}\n```\n'
        '正文。\n```agent-opinion\n{"signal":"bearish"}\n```'
    )
    _, opinion = parse_opinion_block("technical", "技术维度", analysis)
    assert opinion is not None and opinion.signal == "bearish"


def test_confidence_is_clamped_and_defaulted():
    assert _clamp01("0.4") == 0.4
    assert _clamp01(3) == 1.0
    assert _clamp01(-2) == 0.0
    assert _clamp01(None) == 0.5
    assert _clamp01("abc") == 0.5

    _, opinion = parse_opinion_block("t", "技术", '```agent-opinion\n{"signal":"bullish","confidence":9}\n```')
    assert opinion is not None and opinion.confidence == 1.0


# --- 分歧分类 --------------------------------------------------------------


@pytest.mark.parametrize(
    ("opinions", "expected"),
    [
        ([], "insufficient_opinions"),
        ([_opinion("t", "bullish"), _opinion("f", "bearish")], "mixed_directional_signals"),
        ([_opinion("t", "bullish"), _opinion("f", "bullish")], "aligned_bullish"),
        ([_opinion("t", "bullish"), _opinion("f", "neutral")], "bullish_with_neutral"),
        ([_opinion("t", "bearish"), _opinion("f", "bearish")], "aligned_bearish"),
        ([_opinion("t", "bearish"), _opinion("f", "neutral")], "bearish_with_neutral"),
        ([_opinion("t", "neutral")], "all_neutral"),
    ],
)
def test_every_conflict_type_is_classified(opinions, expected):
    assert classify_disagreement(opinions).conflict_type == expected


def test_risk_veto_overrides_the_directional_hint():
    """硬性否决：风险维度高风险看空 → 综合不得买入，且提示必须优先执行否决。"""
    summary = classify_disagreement([
        _opinion("technical", "bullish"),
        _opinion("risk", "bearish", risk="high"),
    ])

    assert summary.risk_veto is True
    assert "风控否决" in summary.decision_path_hint
    assert summary.conflict_type == "mixed_directional_signals"


@pytest.mark.parametrize(
    ("signal", "risk"),
    [("bullish", "high"), ("bearish", "medium"), ("bearish", "low"), ("bearish", "none")],
)
def test_risk_veto_needs_high_risk_and_bearish(signal, risk):
    summary = classify_disagreement([_opinion("risk", signal, risk=risk)])
    assert summary.risk_veto is False


def test_veto_only_applies_to_the_risk_agent():
    summary = classify_disagreement([_opinion("technical", "bearish", risk="high")])
    assert summary.risk_veto is False


# --- 综合指引 --------------------------------------------------------------


def _result(name: str, opinion: AgentOpinion | None) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=name, display_name=opinion.display_name if opinion else name,
        analysis="正文", opinion=opinion,
    )


def test_guidance_is_empty_without_opinions():
    assert build_synthesis_guidance({}) == ""
    assert build_synthesis_guidance({"t": _result("technical", None)}) == ""


def test_guidance_lists_buckets_and_conflict_type():
    guidance = build_synthesis_guidance({
        "technical": _result("technical", _opinion("technical", "bullish")),
        "fundamental": _result("fundamental", _opinion("fundamental", "bearish")),
    })

    assert "## Agent 分歧摘要" in guidance
    assert "mixed_directional_signals" in guidance
    assert "technical维度" in guidance and "fundamental维度" in guidance


def test_veto_constraint_is_placed_first_so_truncation_cannot_drop_it():
    guidance = build_synthesis_guidance({
        "risk": _result("risk", _opinion("risk", "bearish", risk="high")),
    })

    first_line = guidance.splitlines()[0]
    assert "硬性风控约束" in first_line, "风控否决必须排在最前，预算截断不得先丢它"
    assert "不得买入" in first_line
