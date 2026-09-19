from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.orchestration.contracts import (
    ExecutionPlan,
    PlanIssue,
    PlanReview,
)


def review_execution_plan(
    plan: ExecutionPlan,
    results: Mapping[str, AgentExecutionResult],
) -> PlanReview:
    issues: list[PlanIssue] = []
    retry_task_ids: list[str] = []

    def add_retry(task_id: str, reason: str) -> None:
        issues.append(PlanIssue(task_id=task_id, reason=reason, retryable=True))
        retry_task_ids.append(task_id)

    for task in plan.tasks:
        result = results.get(task.agent_name)
        if result is None:
            add_retry(task.task_id, "任务没有返回结果")
            continue
        if result.status == "failed":
            if result.retryable:
                add_retry(task.task_id, "任务执行失败")
            else:
                issues.append(
                    PlanIssue(
                        task_id=task.task_id,
                        reason="任务执行失败，当前错误不可通过重试恢复",
                        retryable=False,
                    )
                )
            continue
        if not result.analysis.strip():
            add_retry(task.task_id, "任务没有生成有效分析")
            continue
        if task.allowed_tools and not result.tools_called:
            add_retry(task.task_id, "任务未调用计划要求的数据工具")
            continue
        if result.tool_results and all(item.is_error for item in result.tool_results):
            add_retry(task.task_id, "任务的工具调用全部失败")
            continue
        if result.status == "partial":
            issues.append(
                PlanIssue(
                    task_id=task.task_id,
                    reason="任务部分完成，将保留已有分析",
                    retryable=False,
                )
            )

    return PlanReview(
        issues=tuple(issues),
        retry_task_ids=tuple(retry_task_ids),
    )


def build_retry_plan(plan: ExecutionPlan, review: PlanReview) -> ExecutionPlan:
    retry_ids = set(review.retry_task_ids)
    tasks = tuple(
        replace(
            task,
            objective=f"{task.objective}；修复上一次执行失败并重新给出完整结论",
            dependencies=(),
        )
        for task in plan.tasks
        if task.task_id in retry_ids
    )
    return ExecutionPlan(
        tasks=tasks,
        reasoning="Reviewer 请求对失败任务进行一次有界重试",
    )
