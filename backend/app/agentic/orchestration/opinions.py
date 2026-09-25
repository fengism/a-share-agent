from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

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

# 单独匹配代码围栏，绝不跨块搜索 signal；裸 JSON 交给解码器处理嵌套结构。
_FENCED_BLOCK_PATTERN = re.compile(r"```([^\n`{]*)\n?(.*?)(```|\Z)", re.DOTALL)
_JSON_START_PATTERN = re.compile(r"[\[{]")


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
    """从 Agent 输出中解析末尾的结构化结论块，支持标准块与容错后备提取。

    Return:
        (剔除结构化块后的正文, 解析出的意见；无有效块时为 None)
    """
    candidates: list[tuple[int, int, object]] = []
    blocks = list(_FENCED_BLOCK_PATTERN.finditer(analysis))
    for block in blocks:
        if block.group(3) != "```":
            continue  # 未闭合的围栏保留正文，也不允许裸 JSON 后备解析进入其中。
        language = block.group(1).strip().lower()
        if language not in {"agent-opinion", "json", ""}:
            continue
        # 无显式标记的 JSON 只接受末尾独立结论，避免把普通数据当作意见。
        if language != "agent-opinion" and analysis[block.end():].strip():
            continue
        try:
            payload = json.loads(block.group(2))
        except (json.JSONDecodeError, ValueError):
            continue
        candidates.append((block.start(), block.end(), payload))

    decoder = json.JSONDecoder()
    consumed = 0
    for match in _JSON_START_PATTERN.finditer(analysis):
        start = match.start()
        if start < consumed or any(block.start() <= start < block.end() for block in blocks):
            continue
        try:
            payload, end = decoder.raw_decode(analysis, start)
        except (json.JSONDecodeError, ValueError):
            continue
        consumed = end  # 跳过完整对象/数组，不能把其中的嵌套对象误当成结论。
        line_start = analysis.rfind("\n", 0, start) + 1
        if analysis[line_start:start].strip() or analysis[end:].strip():
            continue
        candidates.append((start, end, payload))

    for start, end, payload in sorted(candidates, key=lambda item: item[0], reverse=True):
        opinion = _parse_opinion_payload(agent_name, display_name, payload)
        if opinion is not None:
            # 校验成功后才移除这一块，其他正文和无效结构化块原样保留。
            cleaned = (analysis[:start] + analysis[end:]).strip()
            return cleaned, opinion
    return analysis, None


def _parse_opinion_payload(
    agent_name: str,
    display_name: str,
    payload: object,
) -> AgentOpinion | None:
    if not isinstance(payload, dict):
        return None

    signal = str(payload.get("signal", "")).strip().lower()
    if signal not in VALID_SIGNALS:
        return None
    risk_text = str(payload.get("risk_level", "none")).strip().lower()
    risk_level: RiskLevel = cast(RiskLevel, risk_text) if risk_text in VALID_RISK_LEVELS else "none"
    opinion = AgentOpinion(
        agent_name=agent_name,
        display_name=display_name,
        signal=signal,  # type: ignore[arg-type]
        confidence=_clamp01(payload.get("confidence", 0.5)),
        risk_level=risk_level,
    )
    return opinion


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
        # 风控否决放在最前，预算截断不得优先丢弃这条硬约束。
        lines.insert(0,
            "- 硬性风控约束: 风险维度高风险看空，最终结论不得买入或加仓，"
            "最高观望（hold），必须列出风险因素"
        )
    return "\n".join(lines)
