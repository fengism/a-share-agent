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

# 重试只带上一轮的结论尾部：结论与结构化观点块在末尾，前文（数据罗列）可以重新取。
_MAX_REPAIR_CONTEXT_CHARACTERS = 4_000
_REPAIR_TRUNCATION_MARKER = "…（上一轮分析前文已按上下文预算截断）\n"


def _bounded_repair_context(analysis: str) -> str:
    text = (analysis or "").strip()
    if not text:
        return ""
    if len(text) <= _MAX_REPAIR_CONTEXT_CHARACTERS:
        return text
    keep = max(0, _MAX_REPAIR_CONTEXT_CHARACTERS - len(_REPAIR_TRUNCATION_MARKER))
    return _REPAIR_TRUNCATION_MARKER + text[-keep:]


def is_usable_task_result(task: AgentTask, result: AgentExecutionResult | None) -> bool:
    """只有具有正文和计划要求证据的结果才可作为依赖上下文。"""
    if result is None or result.outcome.status == "failed" or not result.analysis.strip():
        return False
    if not task.allowed_tools:
        return True
    return bool(result.tools_called and result.has_context_evidence)


def review_execution_plan(
    plan: ExecutionPlan,
    results: Mapping[str, AgentExecutionResult],
) -> PlanReview:
    issues: list[PlanIssue] = []
    retry_task_ids: list[str] = []

    def add_issue(task_id: str, reason: str, *, retryable: bool) -> None:
        issues.append(PlanIssue(task_id=task_id, reason=reason, retryable=retryable))
        if retryable:
            retry_task_ids.append(task_id)

    for task in plan.tasks:
        result = results.get(task.agent_name)
        if result is None:
            add_issue(task.task_id, "任务没有返回结果", retryable=True)
            continue
        outcome = result.outcome
        if outcome.reason.fatal:
            add_issue(task.task_id, outcome.reason.description, retryable=False)
            continue
        # Retryability only controls replay. It must never suppress a coverage
        # issue, nor turn a failed result into a usable dependency.
        if outcome.status == "failed":
            add_issue(task.task_id, "任务执行失败" if result.retryable else "任务执行失败，当前错误不可通过重试恢复",
                      retryable=result.retryable)
            continue
        if task.allowed_tools and not is_usable_task_result(task, result):
            if not result.tools_called:
                reason = "任务未调用计划要求的数据工具"
            elif result.tool_results and all(item.is_error for item in result.tool_results):
                reason = "任务的工具调用全部失败"
            elif result.tool_results and all(item.skipped for item in result.tool_results):
                reason = "任务的工具调用全部被跳过（预算不足或重复），未取得有效证据"
            else:
                reason = "工具结果未形成可用于分析的上下文证据"
            add_issue(task.task_id, reason, retryable=result.retryable)
            continue
        # Cached/replayed tool results with genuine context evidence are usable,
        # even if every summary has skipped=True. No redundant research replay.
        if outcome.status == "partial":
            reason = (f"{outcome.reason.description}，将保留已有分析" if outcome.reason.code not in {"", "stop"}
                      else "任务部分完成，将保留已有分析")
            add_issue(task.task_id, reason, retryable=False)

    return PlanReview(
        issues=tuple(issues),
        retry_task_ids=tuple(retry_task_ids),
    )


def build_retry_plan(
    plan: ExecutionPlan,
    review: PlanReview,
    results: Mapping[str, AgentExecutionResult] | None = None,
) -> ExecutionPlan:
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

    def repair_context(task: AgentTask) -> str:
        """上一轮已有的分析，供重试时保留成立的部分，避免整段重新推导。"""
        if results is None:
            return ""
        previous = results.get(task.agent_name)
        return _bounded_repair_context(previous.analysis) if previous is not None else ""

    tasks = tuple(
        replace(
            task,
            objective=(
                f"{task.objective}；【上一轮执行问题：{issue_reasons[task.task_id]}】"
                "请务必调用相关工具补齐数据证据，修复失败并重新给出完整客观结论。"
                if task.task_id in issue_reasons
                else f"{task.objective}；修复上一次执行失败并重新给出完整结论"
            ),
            repair_context=repair_context(task),
        ) if task.task_id in retry_ids else task
        for task in plan.tasks
    )
    return ExecutionPlan(
        tasks=tasks,
        reasoning="Reviewer 请求对失败任务及受影响的下游进行一次有界重试",
        reuse_task_ids=tuple(task.task_id for task in plan.tasks if task.task_id not in retry_ids),
    )
