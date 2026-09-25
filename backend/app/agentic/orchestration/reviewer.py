from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.orchestration.contracts import (
    AgentTask,
    ExecutionPlan,
    PlanIssue,
    PlanReview,
)


def is_usable_task_result(task: AgentTask, result: AgentExecutionResult | None) -> bool:
    """只有具有正文和计划要求证据的结果才可作为依赖上下文。"""
    return bool(
        result is not None
        and result.status != "failed"
        and result.analysis.strip()
        and (not task.allowed_tools or result.tools_called)
        and (not result.tool_results or any(not item.is_error for item in result.tool_results))
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
        if not result.retryable:
            if result.status == "partial":
                issues.append(PlanIssue(task_id=task.task_id, reason="模型输出中断，将保留已有分析", retryable=False))
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
    # 任一上游重算都会使全部传递下游失效，不得留下基于旧上下文的成功结果。
    while True:
        affected = retry_ids | {
            task.task_id for task in plan.tasks if set(task.dependencies) & retry_ids
        }
        if affected == retry_ids:
            break
        retry_ids = affected
    issue_reasons = {
        issue.task_id: issue.reason
        for issue in review.issues
        if issue.task_id in retry_ids and issue.reason
    }
    tasks = tuple(
        replace(
            task,
            objective=(
                f"{task.objective}；【上一轮执行问题：{issue_reasons[task.task_id]}】"
                "请务必调用相关工具补齐数据证据，修复失败并重新给出完整客观结论。"
                if task.task_id in issue_reasons
                else f"{task.objective}；修复上一次执行失败并重新给出完整结论"
            ),
        ) if task.task_id in retry_ids else task
        for task in plan.tasks
    )
    return ExecutionPlan(
        tasks=tasks,
        reasoning="Reviewer 请求对失败任务及受影响的下游进行一次有界重试",
        reuse_task_ids=tuple(task.task_id for task in plan.tasks if task.task_id not in retry_ids),
    )
