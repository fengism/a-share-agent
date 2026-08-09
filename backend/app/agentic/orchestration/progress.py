from __future__ import annotations

from app.agentic.events import (
    AgentEvent,
    AgentPlan,
    AgentPlanStep,
    AgentPlanStepStatus,
    AgentPlanStepUpdate,
)
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan


def build_plan_event(plan: ExecutionPlan) -> AgentEvent:
    return AgentEvent(
        type="plan",
        plan=AgentPlan(
            summary=plan.reasoning or None,
            steps=[
                AgentPlanStep(
                    id=task.task_id,
                    title=task.display_name,
                    description=task.objective,
                    agent_name=task.agent_name,
                    dependencies=list(task.dependencies),
                )
                for task in plan.tasks
            ],
        ),
    )


def build_task_progress_event(
    task: AgentTask,
    status: AgentPlanStepStatus,
    *,
    detail: str | None = None,
    attempt: int = 1,
) -> AgentEvent:
    return build_step_progress_event(
        task.task_id,
        status,
        detail=detail,
        attempt=attempt,
    )


def build_step_progress_event(
    step_id: str,
    status: AgentPlanStepStatus,
    *,
    detail: str | None = None,
    attempt: int = 1,
) -> AgentEvent:
    return AgentEvent(
        type="plan_step",
        plan_step=AgentPlanStepUpdate(
            step_id=step_id,
            status=status,
            detail=detail,
            attempt=attempt,
        ),
    )
