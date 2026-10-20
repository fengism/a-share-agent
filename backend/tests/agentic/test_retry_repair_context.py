"""Targeted retry: a failed task keeps its previous conclusions instead of re-deriving them."""

from __future__ import annotations

from dataclasses import replace

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.orchestration.contracts import (
    AgentTask,
    ExecutionPlan,
    PlanIssue,
    PlanReview,
)
from app.agentic.orchestration.executor import _build_task_message
from app.agentic.orchestration.reviewer import (
    _MAX_REPAIR_CONTEXT_CHARACTERS,
    _bounded_repair_context,
    build_retry_plan,
)


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        tasks=(
            AgentTask(
                task_id="fundamental",
                agent_name="fundamental",
                display_name="基本面",
                objective="评估基本面",
                allowed_tools=("get_stock_info",),
            ),
            AgentTask(
                task_id="risk",
                agent_name="risk",
                display_name="风险",
                objective="评估下行风险",
                allowed_tools=("get_stock_risk_data",),
                dependencies=("fundamental",),
            ),
        ),
        reasoning="test",
    )


def _result(agent_name: str, analysis: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=agent_name,
        display_name=agent_name,
        analysis=analysis,
    )


def _review(*task_ids: str) -> PlanReview:
    return PlanReview(
        issues=tuple(
            PlanIssue(task_id=task_id, reason="任务未调用计划要求的数据工具", retryable=True)
            for task_id in task_ids
        ),
        retry_task_ids=tuple(task_ids),
    )


def test_repair_context_is_empty_for_short_analyses_only():
    assert _bounded_repair_context("") == ""
    assert _bounded_repair_context("   ") == ""
    assert _bounded_repair_context("结论：估值偏高") == "结论：估值偏高"


def test_repair_context_keeps_the_tail_and_marks_truncation():
    bounded = _bounded_repair_context("前文" * 20_000 + "最终结论：风险可控")

    assert len(bounded) <= _MAX_REPAIR_CONTEXT_CHARACTERS
    assert bounded.startswith("…（上一轮分析前文已按上下文预算截断）")
    # The conclusion (tail) is what a repair must preserve.
    assert bounded.endswith("最终结论：风险可控")


def test_retry_plan_carries_previous_analysis_for_retried_tasks():
    results = {
        "fundamental": _result("fundamental", "上一轮基本面结论"),
        "risk": _result("risk", "上一轮风险结论"),
    }
    retry_plan = build_retry_plan(_plan(), _review("fundamental"), results)

    by_id = {task.task_id: task for task in retry_plan.tasks}
    assert by_id["fundamental"].repair_context == "上一轮基本面结论"
    # Downstream of a retried upstream is re-run too, and also keeps its own work.
    assert by_id["risk"].repair_context == "上一轮风险结论"


def test_retry_plan_without_results_stays_backward_compatible():
    retry_plan = build_retry_plan(_plan(), _review("fundamental"))

    by_id = {task.task_id: task for task in retry_plan.tasks}
    assert by_id["fundamental"].repair_context == ""
    assert "上一轮执行问题" in by_id["fundamental"].objective


def test_task_message_renders_repair_context_before_the_objective():
    task = replace(
        _plan().tasks[0],
        objective="评估基本面；修复上一次执行失败并重新给出完整结论",
        repair_context="上一轮基本面结论：营收增长 12%",
    )

    message = _build_task_message(task, "茅台怎么样", {})

    assert "## 上一轮分析（本轮需要修复）" in message
    assert "上一轮基本面结论：营收增长 12%" in message
    # The objective is the final instruction, so it must come after the material.
    assert message.index("上一轮基本面结论") < message.index("## 当前任务指示与要求")


def test_task_message_omits_repair_section_for_first_run():
    message = _build_task_message(_plan().tasks[0], "茅台怎么样", {})

    assert "上一轮分析" not in message
