"""外层调研循环的纯决策逻辑（research_policy.py）。

这些函数决定「还要不要再跑一轮」「缺口轮给哪些工具」「缺口消息说什么」。它们没有副作用，
因此可以逐条覆盖；`research.py` 的主循环只剩编排。
"""

from __future__ import annotations

import pytest

from app.agentic.contracts import (
    AgentEvidence,
    AgentResearchSpec,
    AgentRoundResult,
    EvidenceRequirement,
)
from app.agentic.research_policy import (
    FOLLOWUP_TOOL_CALL_RESERVE,
    build_gap_message,
    followup_reserve,
    missing_requirements,
    normalize_round_result,
    select_gap_tools,
    should_continue,
)
from app.domain.llm import LLMInvalidResponseError

_DOC = "web_fetch"
_FIN = "get_stock_financial"
_SEARCH = "web_search"


def _evidence(tool_name: str, content: str = '{"ok":true,"data":{"v":1}}', *, is_error: bool = False) -> AgentEvidence:
    return AgentEvidence(
        tool_call_id=f"call-{tool_name}-{len(content)}", tool_name=tool_name,
        arguments="{}", content=content, is_error=is_error,
    )


def _spec(**overrides) -> AgentResearchSpec:
    defaults = {
        "name": "probe", "display_name": "探针", "system_prompt": "sys",
        "tool_names": (_SEARCH, _DOC, _FIN),
        "requirements": (
            EvidenceRequirement(key="doc", label="公告正文", tool_names=(_DOC,)),
            EvidenceRequirement(key="fin", label="财务数据", tool_names=(_FIN,)),
        ),
    }
    defaults.update(overrides)
    return AgentResearchSpec(**defaults)  # type: ignore[arg-type]


# --- missing_requirements --------------------------------------------------


def test_missing_requirements_reports_only_unsatisfied_dimensions():
    spec = _spec()
    assert [item.key for item in missing_requirements(spec.requirements, [])] == ["doc", "fin"]
    assert [item.key for item in missing_requirements(spec.requirements, [_evidence(_DOC)])] == ["fin"]
    assert missing_requirements(spec.requirements, [_evidence(_DOC), _evidence(_FIN)]) == []


def test_evidence_from_an_unrelated_tool_does_not_satisfy_a_requirement():
    spec = _spec()
    assert [item.key for item in missing_requirements(spec.requirements, [_evidence(_SEARCH)])] == ["doc", "fin"]


def test_error_evidence_does_not_satisfy_a_requirement():
    spec = _spec()
    error = _evidence(_DOC, '{"ok":false,"error":{"code":"timeout"}}', is_error=True)
    assert [item.key for item in missing_requirements(spec.requirements, [error])] == ["doc", "fin"]


def test_validator_can_reject_evidence_for_the_right_tool():
    requirement = EvidenceRequirement(
        key="doc", label="公告正文", tool_names=(_DOC,),
        validator=lambda item: "公告" in item.content,
    )
    assert missing_requirements((requirement,), [_evidence(_DOC, '{"ok":true,"data":{"v":1}}')])
    assert not missing_requirements((requirement,), [_evidence(_DOC, '{"ok":true,"data":"公告"}')])


# --- select_gap_tools ------------------------------------------------------


def test_gap_tools_are_limited_to_the_missing_dimensions():
    spec = _spec()
    missing = missing_requirements(spec.requirements, [_evidence(_DOC)])
    assert select_gap_tools(spec, missing) == (_FIN,)


def test_document_gap_also_brings_discovery_tools():
    """正文没读到时光给 web_fetch 没用：得先能发现要读什么。"""
    spec = _spec()
    missing = missing_requirements(spec.requirements, [_evidence(_FIN)])
    assert select_gap_tools(spec, missing) == (_SEARCH, _DOC)


def test_discovery_tools_are_only_added_when_the_spec_has_them():
    spec = _spec(tool_names=(_DOC, _FIN))
    missing = missing_requirements(spec.requirements, [_evidence(_FIN)])
    assert select_gap_tools(spec, missing) == (_DOC,)


def test_gap_tools_preserve_the_spec_order():
    spec = _spec()
    both = missing_requirements(spec.requirements, [])
    assert select_gap_tools(spec, both) == (_SEARCH, _DOC, _FIN)


# --- should_continue -------------------------------------------------------


def _continue(**overrides) -> bool:
    base = {
        "missing": [EvidenceRequirement(key="k", label="l", tool_names=(_DOC,))],
        "current_round": 2, "max_rounds": 3, "stop_reason": "",
        "tool_calls_remaining": 5, "made_progress": True,
    }
    base.update(overrides)
    return should_continue(**base)  # type: ignore[arg-type]


def test_continue_only_when_every_condition_holds():
    assert _continue() is True
    assert _continue(missing=[]) is False
    assert _continue(made_progress=False) is False
    assert _continue(current_round=3) is False
    assert _continue(stop_reason="预算不足") is False
    assert _continue(tool_calls_remaining=0) is False
    # None 表示额度未知，不等于耗尽。
    assert _continue(tool_calls_remaining=None) is True


# --- followup_reserve ------------------------------------------------------


def test_followup_reserve_only_applies_when_there_are_more_rounds():
    assert followup_reserve(1) == 0
    assert followup_reserve(2) == FOLLOWUP_TOOL_CALL_RESERVE
    assert FOLLOWUP_TOOL_CALL_RESERVE == 8


# --- build_gap_message -----------------------------------------------------


def test_gap_message_lists_labels_and_previous_summary():
    message = build_gap_message(
        "原始任务", AgentRoundResult(summary="上一轮摘要"),
        [_evidence(_DOC)], missing_requirements(_spec().requirements, [_evidence(_DOC)]),
    )

    assert "原始调研任务：原始任务" in message
    assert "前序调研摘要：上一轮摘要" in message
    assert "缺失证据维度（第 2 轮）：财务数据" in message
    assert "必须实际调用工具" in message
    assert "已有工具证据：" in message


def test_gap_message_handles_an_empty_previous_summary():
    message = build_gap_message(
        "任务", AgentRoundResult(summary=""),
        [], missing_requirements(_spec().requirements, []),
    )
    assert "前序调研摘要：暂无结论" in message


def test_gap_message_switches_the_retry_hint_when_guidance_is_provided():
    without = build_gap_message("任务", AgentRoundResult(summary=""), [], [])
    with_guidance = build_gap_message(
        "任务", AgentRoundResult(summary=""), [], [], document_search_guidance="先复用目录",
    )

    assert "不得原样重复失败或低质量的查询" in without
    assert "先复用目录" in with_guidance
    assert "不得原样重复失败或低质量的查询" not in with_guidance


# --- normalize_round_result ------------------------------------------------


def test_fatal_round_reason_is_raised():
    result = AgentRoundResult(summary="半截", termination_reason="authentication_error")
    with pytest.raises(LLMInvalidResponseError):
        normalize_round_result(result)


def test_failed_or_stopped_round_loses_its_summary():
    assert normalize_round_result(
        AgentRoundResult(summary="半截", execution_status="failed")
    ).summary == ""
    assert normalize_round_result(
        AgentRoundResult(summary="半截", stop_reason="提前收尾")
    ).summary == ""
    # 注意 insufficient_evidence 是「可保留已获证据」，不是失败：摘要要留下。
    kept = normalize_round_result(
        AgentRoundResult(summary="半截", termination_reason="insufficient_evidence")
    )
    assert kept.summary == "半截"
    assert kept.outcome.status != "failed"


def test_healthy_round_is_returned_unchanged():
    result = AgentRoundResult(summary="结论", evidence=(_evidence(_DOC),), tool_calls_remaining=3)
    assert normalize_round_result(result) is result
