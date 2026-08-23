from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.agentic.agents.contracts import AgentExecutionResult

Signal = Literal["bullish", "bearish", "neutral"]
RiskLevel = Literal["high", "medium", "low", "none"]

VALID_SIGNALS: frozenset[str] = frozenset({"bullish", "bearish", "neutral"})
VALID_RISK_LEVELS: frozenset[str] = frozenset({"high", "medium", "low", "none"})

# 各专业 Agent 的结论权重（技术 40% / 基本面+情报 45% / 风险 15%），
# 仅作为综合 prompt 的指引，不是程序化计算。
AGENT_WEIGHTS: dict[str, float] = {
    "technical": 0.40,
    "fundamental": 0.25,
    "news": 0.20,
    "risk": 0.15,
}

_OPINION_BLOCK_PATTERN = re.compile(
    r"```agent-opinion\s*\n(.*?)\n```",
    re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class AgentOpinion:
    """单个 Agent 的归一化结论，用于分歧计算与风控约束。"""

    agent_name: str
    display_name: str
    signal: Signal
    confidence: float
    risk_level: RiskLevel = "none"


def _clamp01(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.5
    return min(1.0, max(0.0, number))


def parse_opinion_block(
    agent_name: str,
    display_name: str,
    analysis: str,
) -> tuple[str, AgentOpinion | None]:
    """从 Agent 输出中解析末尾的 ```agent-opinion``` 结构化块。

    Return:
        (剔除结构化块后的正文, 解析出的意见；无有效块时为 None)
    """
    match = _OPINION_BLOCK_PATTERN.search(analysis)
    if match is None:
        return analysis, None
    cleaned = analysis[: match.start()].rstrip() + analysis[match.end():]
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return cleaned, None
    if not isinstance(payload, dict):
        return cleaned, None

    signal = str(payload.get("signal", "")).strip().lower()
    if signal not in VALID_SIGNALS:
        return cleaned, None
    risk_text = str(payload.get("risk_level", "none")).strip().lower()
    risk_level: RiskLevel = risk_text if risk_text in VALID_RISK_LEVELS else "none"
    opinion = AgentOpinion(
        agent_name=agent_name,
        display_name=display_name,
        signal=signal,  # type: ignore[arg-type]
        confidence=_clamp01(payload.get("confidence", 0.5)),
        risk_level=risk_level,
    )
    return cleaned, opinion


@dataclass(frozen=True, slots=True)
class DisagreementSummary:
    """多 Agent 结论分歧的低敏感摘要。"""

    conflict_type: str
    decision_path_hint: str
    bullish: tuple[str, ...]
    bearish: tuple[str, ...]
    neutral: tuple[str, ...]
    risk_veto: bool


def classify_disagreement(opinions: list[AgentOpinion]) -> DisagreementSummary:
    """把有效意见分桶并分类冲突类型，产出决策路径提示。"""
    bullish = tuple(o.display_name for o in opinions if o.signal == "bullish")
    bearish = tuple(o.display_name for o in opinions if o.signal == "bearish")
    neutral = tuple(o.display_name for o in opinions if o.signal == "neutral")

    if bullish and bearish:
        conflict_type = "mixed_directional_signals"
        hint = "先解释各 Agent 结论冲突的可能原因，再给出保守的综合结论"
    elif not opinions:
        conflict_type = "insufficient_opinions"
        hint = "缺乏有效结构化意见，倾向保守观望并明确说明数据局限"
    elif bullish and not bearish:
        conflict_type = "aligned_bullish" if not neutral else "bullish_with_neutral"
        hint = "多方意见一致，可给出偏多结论但仍需引用关键风险"
    elif bearish and not bullish:
        conflict_type = "aligned_bearish" if not neutral else "bearish_with_neutral"
        hint = "空方意见一致，结论应偏谨慎"
    else:
        conflict_type = "all_neutral"
        hint = "各维度均无明确方向，结论应为观望/震荡"

    # 确定性风控否决：风险 Agent 高风险看空 → 综合结论不得买入
    risk_veto = any(
        o.agent_name == "risk" and o.risk_level == "high" and o.signal == "bearish"
        for o in opinions
    )
    if risk_veto:
        hint = "风险 Agent 判定高风险且看空，必须优先执行风控否决"

    return DisagreementSummary(
        conflict_type=conflict_type,
        decision_path_hint=hint,
        bullish=bullish,
        bearish=bearish,
        neutral=neutral,
        risk_veto=risk_veto,
    )


def build_synthesis_guidance(results: Mapping[str, AgentExecutionResult]) -> str:
    """构建注入综合 prompt 的分歧摘要与硬约束块（无意见时返回空串）。"""
    opinions = [result.opinion for result in results.values() if result.opinion is not None]
    if not opinions:
        return ""
    summary = classify_disagreement(opinions)
    lines = [
        "## Agent 分歧摘要（结构化元信息，供综合决策参考）",
        f"- 多方: {', '.join(summary.bullish) or '无'}",
        f"- 空方: {', '.join(summary.bearish) or '无'}",
        f"- 中性: {', '.join(summary.neutral) or '无'}",
        f"- 冲突类型: {summary.conflict_type}",
        f"- 决策路径: {summary.decision_path_hint}",
        "- 信号权重参考: 技术 40% / 基本面 25% / 情报 20% / 风险 15%（缺失维度按剩余归一化）",
    ]
    if summary.risk_veto:
        lines.append(
            "- 硬性风控约束: 风险维度判定为高风险，最终结论不得给出买入或加仓建议，"
            "最高只能给观望（hold），并必须显著列出风险因素"
        )
    return "\n".join(lines)
