"""取证缺口报告：纯字符串、无原始载荷，且每个状态都要有独立措辞。

这些文案是「分析没做成」时用户唯一能看到的东西，之前只有 51% 覆盖、整段分支没测。
"""

from __future__ import annotations

from app.agentic.agents.contracts import AgentExecutionResult, ToolExecutionSummary
from app.agentic.runtime.evidence import (
    build_evidence_gap_report,
    decode_tool_payload,
    evidence_gap_reason,
    failure_label,
    flatten_text,
    has_finite_number,
    safe_tool_failure_code,
    tool_failure_label,
)


def _result(
    agent: str = "technical",
    *,
    tools: tuple[ToolExecutionSummary, ...] = (),
    analysis: str = "分析",
    errors: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    termination_reason: str = "stop",
) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=agent,
        display_name=agent,
        analysis=analysis,
        tool_results=list(tools),
        errors=list(errors),
        warnings=list(warnings),
        termination_reason=termination_reason,
    )


def _tool(**kwargs) -> ToolExecutionSummary:
    defaults = {"name": "t", "is_error": False, "has_evidence": True, "context_has_evidence": True}
    defaults.update(kwargs)
    return ToolExecutionSummary(**defaults)


# --- 解码辅助 ---------------------------------------------------------------


def test_decode_unwraps_only_successful_envelopes():
    assert decode_tool_payload('{"ok":true,"data":{"v":1}}') == {"v": 1}
    assert decode_tool_payload('{"ok":false,"error":{"code":"timeout"}}') == {
        "ok": False, "error": {"code": "timeout"},
    }
    assert decode_tool_payload("plain text") == "plain text"
    assert decode_tool_payload("") == ""


def test_flatten_text_joins_every_shape():
    assert flatten_text("abc") == "abc"
    assert flatten_text({"a": "x", "b": ["y", None]}) == "x\ny\n"
    assert flatten_text(3) == "3"
    assert flatten_text(None) == ""


def test_has_finite_number_ignores_bools_and_non_finite():
    assert has_finite_number(1.5) is True
    assert has_finite_number(True) is False
    assert has_finite_number(float("nan")) is False
    assert has_finite_number({"a": [1, 2]}) is True
    assert has_finite_number({"a": "1"}) is False
    assert has_finite_number([]) is False


# --- 失败码 ----------------------------------------------------------------


def test_failure_code_only_accepts_known_allowlisted_codes():
    assert safe_tool_failure_code('{"ok":false,"error":{"code":"timeout"}}') == "timeout"
    # 未登记的错误码一律不落到用户可见文案里。
    assert safe_tool_failure_code('{"ok":false,"error":{"code":"some_internal_thing"}}') == ""
    assert safe_tool_failure_code('{"ok":true,"data":{}}') == ""
    assert safe_tool_failure_code("not json") == ""
    assert failure_label("") == "工具调用失败"
    assert tool_failure_label('{"ok":false,"error":{"code":"rate_limited"}}') == "数据源请求受限"


# --- 缺口原因 --------------------------------------------------------------


def test_gap_reason_lists_each_distinct_problem():
    reason = evidence_gap_reason(
        _result(
            tools=(
                _tool(name="a", is_error=True, has_evidence=False, context_has_evidence=False),
                _tool(name="b", has_evidence=False, context_has_evidence=False),
                _tool(name="c", skipped=True, has_evidence=False, context_has_evidence=False),
            )
        )
    )
    assert "部分工具调用失败" in reason
    assert "部分工具未返回有效数据" in reason
    assert "部分工具请求未执行或被合并复用" in reason


def test_gap_reason_flags_evidence_that_never_reached_the_model():
    reason = evidence_gap_reason(
        _result(tools=(_tool(has_evidence=True, context_has_evidence=False),))
    )
    assert "部分已获取数据未进入模型上下文" in reason


def test_gap_reason_flags_a_run_with_only_instruction_results():
    reason = evidence_gap_reason(_result(tools=(_tool(name="load_skill", instruction=True),)))
    assert "未取得数据工具结果" in reason


def test_gap_reason_never_claims_everything_is_fine():
    """即使所有工具都成功，也不能输出空字符串让上层以为没有缺口。"""
    reason = evidence_gap_reason(_result(tools=(_tool(),)))
    assert reason
    assert "未完整完成" in reason


# --- 报告本体 --------------------------------------------------------------


def test_report_categorizes_every_tool_state():
    report = build_evidence_gap_report([
        _result(
            "technical",
            tools=(
                _tool(name="load_skill", instruction=True),
                _tool(name="ok"),
                _tool(name="skip", skipped=True, has_evidence=False, context_has_evidence=False),
                _tool(name="err", is_error=True, has_evidence=False, context_has_evidence=False),
                _tool(name="hidden", has_evidence=True, context_has_evidence=False),
                _tool(name="empty", has_evidence=False, context_has_evidence=False),
            ),
        )
    ])
    assert "技术面" in report
    for label in ("Skill 指令 1 条", "上下文有效 1 条", "已跳过或复用 1 条", "失败 1 条", "未进入上下文 1 条", "无有效数据 1 条"):
        assert label in report, label


def test_report_caps_the_number_of_dimensions():
    report = build_evidence_gap_report([_result("technical") for _ in range(11)])
    assert "另有 3 个维度未展开" in report


def test_report_handles_an_empty_run():
    report = build_evidence_gap_report([])
    assert "没有可用分析记录" in report


def test_report_never_contains_raw_payload_or_model_prose():
    secret = "sk-live-abcdef"
    report = build_evidence_gap_report([
        _result("risk", analysis=secret, errors=(secret,), warnings=(secret,))
    ])
    assert secret not in report
