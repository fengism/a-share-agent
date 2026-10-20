"""Outer research loop policy: pure decisions, no I/O and no events.

``research.py`` 的主循环此前把这些判断和事件发射、会话调用混在一起，导致 150 行
主循环几乎无法单独测试。这里只保留「给定状态，下一步该做什么」的纯函数：

- 哪些证据需求还缺（``missing_requirements``）
- 缺口轮该下发哪些工具（``select_gap_tools``）
- 要不要再跑一轮（``should_continue``）
- 缺口消息长什么样（``build_gap_message``）
- 给后续补查预留多少额度（``followup_reserve``）
- 一轮结果如何归一化（``normalize_round_result``）

没有副作用，因此可以逐条覆盖，主循环退化为纯编排。
"""

from __future__ import annotations

from dataclasses import replace

from app.agentic.contracts import (
    AgentEvidence,
    AgentResearchSpec,
    AgentRoundResult,
    EvidenceRequirement,
    render_agent_evidence,
)
from app.domain.llm import LLMInvalidResponseError

#: 首轮为后续补查预留的工具调用数。放在这里而不是散在循环里，避免变成第二个魔法数。
FOLLOWUP_TOOL_CALL_RESERVE = 8

_DISCOVERY_TOOLS = frozenset({"web_search", "iwencai_search"})
_DOCUMENT_TOOLS = frozenset({"web_fetch", "fetch_urls"})


def missing_requirements(
    requirements: tuple[EvidenceRequirement, ...],
    evidence: list[AgentEvidence],
) -> list[EvidenceRequirement]:
    return [
        requirement
        for requirement in requirements
        if not any(requirement.accepts(item) for item in evidence)
    ]


def select_gap_tools(
    spec: AgentResearchSpec,
    missing: list[EvidenceRequirement],
) -> tuple[str, ...]:
    """Tools for a gap round: only what the missing dimensions need.

    缺口是「正文没读到」时，光给 ``web_fetch`` 没用——还得能先发现要读什么，所以把
    发现类工具一起带上（仅限 spec 里确实有的）。
    """
    required_tools = {
        tool_name
        for requirement in missing
        for tool_name in requirement.tool_names
    }
    if required_tools.intersection(_DOCUMENT_TOOLS):
        required_tools.update(_DISCOVERY_TOOLS.intersection(spec.tool_names))
    return tuple(tool_name for tool_name in spec.tool_names if tool_name in required_tools)


def should_continue(
    *,
    missing: list[EvidenceRequirement],
    current_round: int,
    max_rounds: int,
    stop_reason: str,
    tool_calls_remaining: int | None,
    made_progress: bool,
) -> bool:
    """Whether another evidence-gap round is worth running.

    ``made_progress`` 是新增的有效证据条数——**不等于**缺口缩小。没有缩小就停，
    否则无关材料会把轮次额度耗光。
    """
    return bool(
        missing
        and made_progress
        and current_round < max_rounds
        and not stop_reason
        and tool_calls_remaining != 0
    )


def followup_reserve(max_rounds: int) -> int:
    """First round reserves room for the follow-up rounds; later rounds release it."""
    return FOLLOWUP_TOOL_CALL_RESERVE if max_rounds > 1 else 0


def build_gap_message(
    original_message: str,
    previous_result: AgentRoundResult,
    evidence: list[AgentEvidence],
    missing: list[EvidenceRequirement],
    round_index: int = 2,
    document_search_guidance: str = "",
) -> str:
    labels = "、".join(item.label for item in missing)
    round_desc = f"第 {round_index} 轮" if round_index > 1 else "本轮"
    return "\n".join([
        f"原始调研任务：{original_message}",
        f"前序调研摘要：{previous_result.summary or '暂无结论'}",
        f"缺失证据维度（{round_desc}）：{labels}",
        "请仅围绕缺失维度继续调用允许的工具补齐证据。必须实际调用工具，不得使用常识补写。",
        ("缺口是待阅读/核对清单，不是一项一个query。先复用已取得的文献与目录，按同一文献/公司合并检查；"
         "仅在阅读后仍缺核心前提时增加窄查询，说明已有材料为何不足。\n" + document_search_guidance)
        if document_search_guidance else
        "先检查已有工具参数，不得原样重复失败或低质量的查询；应根据缺失维度缩小范围并改进检索词。",
        "已有工具证据：",
        render_agent_evidence(evidence),
    ])


def normalize_round_result(result: AgentRoundResult) -> AgentRoundResult:
    """Fail closed on a round result before it can be used as evidence.

    可插拔的 Runtime 必须和默认适配器守同一条边界：状态标志不能覆盖致命/未知原因。
    """
    outcome = result.outcome
    if outcome.reason.fatal:
        raise LLMInvalidResponseError(
            f"Agent 调研停止：{outcome.reason.description}（reason={outcome.reason.code}）"
        )
    if result.execution_status == "failed" or outcome.status == "failed" or result.stop_reason:
        return replace(result, summary="")
    return result
