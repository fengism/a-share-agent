"""Reviewer：决定重试哪些任务、以及哪些结果可以当依赖上下文。

这段逻辑此前完全没有测试（`review_execution_plan` 主体 0 覆盖），而它的两个输出
——`retry_task_ids` 和 `reuse_task_ids`——直接决定多花几轮 LLM 还是静默用陈旧结论。
"""

from __future__ import annotations

from app.agentic.agents.contracts import AgentExecutionResult, ToolExecutionSummary
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.reviewer import (
    _MAX_REPAIR_CONTEXT_CHARACTERS,
    build_retry_plan,
    is_usable_task_result,
    review_execution_plan,
)

_TOOL = ("fake_tool",)


def _task(task_id: str, *, dependencies: tuple[str, ...] = (), tools=_TOOL) -> AgentTask:
    return AgentTask(
        task_id=task_id,
        agent_name=task_id,
        display_name=task_id,
        objective=f"{task_id} 目标",
        allowed_tools=tools,
        dependencies=dependencies,
    )


def _plan(*tasks: AgentTask) -> ExecutionPlan:
    return ExecutionPlan(tasks=tasks, reuse_task_ids=(), reasoning="t")


def _tool(*, is_error: bool = False, context: bool = True, skipped: bool = False) -> ToolExecutionSummary:
    return ToolExecutionSummary(
        name="fake_tool",
        is_error=is_error,
        has_evidence=context,
        context_has_evidence=context,
        skipped=skipped,
    )


def _result(
    name: str,
    *,
    analysis: str = "结论",
    tools=("fake_tool",),
    summaries: tuple[ToolExecutionSummary, ...] | None = None,
    status: str = "completed",
    retryable: bool = True,
    termination_reason: str = "",
) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=name,
        display_name=name,
        analysis=analysis,
        status=status,  # type: ignore[arg-type]
        tools_called=list(tools),
        tool_results=list(summaries if summaries is not None else [_tool()]),
        retryable=retryable,
        termination_reason=termination_reason,
    )


# --- is_usable_task_result -------------------------------------------------


def test_result_without_tools_is_usable_when_the_task_needs_none():
    task = _task("plain", tools=())
    assert is_usable_task_result(task, _result("plain", tools=())) is True


def test_result_needs_tool_calls_and_context_evidence():
    task = _task("a")
    assert is_usable_task_result(task, _result("a")) is True
    assert is_usable_task_result(task, _result("a", tools=())) is False
    assert is_usable_task_result(
        task, _result("a", summaries=(_tool(context=False),))
    ) is False
    assert is_usable_task_result(task, _result("a", analysis="   ")) is False
    assert is_usable_task_result(task, _result("a", status="failed")) is False
    assert is_usable_task_result(task, None) is False


# --- review_execution_plan -------------------------------------------------


def test_missing_result_is_retryable():
    review = review_execution_plan(_plan(_task("a")), {})
    assert review.retry_task_ids == ("a",)
    assert "没有返回结果" in review.issues[0].reason


def test_fatal_reason_is_never_retried():
    review = review_execution_plan(
        _plan(_task("a")),
        {"a": _result("a", status="failed", termination_reason="upstream_unavailable")},
    )
    assert review.retry_task_ids == ()
    assert review.issues[0].retryable is False


def test_failed_task_respects_the_retryable_flag():
    retryable = review_execution_plan(
        _plan(_task("a")), {"a": _result("a", status="failed")}
    )
    assert retryable.retry_task_ids == ("a",)

    permanent = review_execution_plan(
        _plan(_task("a")), {"a": _result("a", status="failed", retryable=False)}
    )
    assert permanent.retry_task_ids == ()
    assert "不可通过重试恢复" in permanent.issues[0].reason


def test_each_missing_evidence_case_gets_its_own_reason():
    cases = {
        "未调用计划要求的数据工具": _result("a", tools=(), summaries=()),
        "工具调用全部失败": _result("a", summaries=(_tool(is_error=True, context=False),)),
        "全部被跳过": _result("a", summaries=(_tool(skipped=True, context=False),)),
        "未形成可用于分析的上下文证据": _result("a", summaries=(_tool(context=False),)),
    }
    for expected, result in cases.items():
        review = review_execution_plan(_plan(_task("a")), {"a": result})
        assert review.retry_task_ids == ("a",), expected
        assert expected in review.issues[0].reason, (expected, review.issues[0].reason)


def test_skipped_results_with_real_context_evidence_are_not_retried():
    """缓存/重放的工具结果有真实上下文证据时可用，不该重跑研究。"""
    review = review_execution_plan(
        _plan(_task("a")),
        {"a": _result("a", summaries=(_tool(skipped=True, context=True),))},
    )
    assert review.retry_task_ids == ()


def test_partial_result_keeps_what_it_has():
    review = review_execution_plan(
        _plan(_task("a")), {"a": _result("a", status="partial", termination_reason="length")}
    )
    assert review.retry_task_ids == ()
    assert review.issues[0].retryable is False
    assert "保留已有分析" in review.issues[0].reason


def test_healthy_plan_has_no_issues():
    review = review_execution_plan(_plan(_task("a")), {"a": _result("a")})
    assert review.issues == ()
    assert review.retry_task_ids == ()


# --- build_retry_plan ------------------------------------------------------


def test_retry_invalidates_all_transitive_downstream_tasks():
    plan = _plan(
        _task("a"),
        _task("b", dependencies=("a",)),
        _task("c", dependencies=("b",)),
        _task("d"),
    )
    review = review_execution_plan(plan, {"a": _result("a", status="failed"),
                                         "b": _result("b"), "c": _result("c"), "d": _result("d")})
    retry = build_retry_plan(plan, review, {})
    assert set(retry.reuse_task_ids) == {"d"}
    assert {task.task_id for task in retry.tasks if task.task_id != "d"} == {"a", "b", "c"}


def test_retry_plan_carries_the_previous_analysis_tail():
    plan = _plan(_task("a"))
    review = review_execution_plan(plan, {"a": _result("a", analysis="旧结论", status="failed")})
    retry = build_retry_plan(plan, review, {"a": _result("a", analysis="旧结论", status="failed")})
    assert retry.tasks[0].repair_context == "旧结论"
    assert "上一轮执行问题" in retry.tasks[0].objective


def test_repair_context_is_bounded_to_the_tail():
    plan = _plan(_task("a"))
    long_analysis = "前" * 10_000 + "尾部结论"
    review = review_execution_plan(plan, {"a": _result("a", status="failed")})
    retry = build_retry_plan(plan, review, {"a": _result("a", analysis=long_analysis, status="failed")})

    context = retry.tasks[0].repair_context
    assert len(context) <= _MAX_REPAIR_CONTEXT_CHARACTERS
    assert context.endswith("尾部结论")
    assert "已按上下文预算截断" in context


def test_retry_plan_without_results_has_no_repair_context():
    plan = _plan(_task("a"))
    review = review_execution_plan(plan, {})
    retry = build_retry_plan(plan, review)
    assert retry.tasks[0].repair_context == ""


def test_downstream_task_gets_a_repair_objective_too():
    plan = _plan(_task("a"), _task("b", dependencies=("a",)))
    review = review_execution_plan(plan, {"a": _result("a", status="failed"), "b": _result("b")})
    retry = build_retry_plan(plan, review, {})
    downstream = next(task for task in retry.tasks if task.task_id == "b")
    assert "修复上一次执行失败" in downstream.objective
