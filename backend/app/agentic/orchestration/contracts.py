from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AgentDescriptor(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def tool_names(self) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class AgentTask:
    task_id: str
    agent_name: str
    display_name: str
    objective: str
    allowed_tools: tuple[str, ...]
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("Agent 任务 ID 不能为空")
        if not self.agent_name.strip():
            raise ValueError("Agent 名称不能为空")
        if not self.objective.strip():
            raise ValueError(f"Agent 任务 {self.task_id!r} 缺少目标")
        if len(self.allowed_tools) != len(set(self.allowed_tools)):
            raise ValueError(f"Agent 任务 {self.task_id!r} 包含重复工具")
        if self.task_id in self.dependencies:
            raise ValueError(f"Agent 任务 {self.task_id!r} 不能依赖自身")


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    tasks: tuple[AgentTask, ...]
    reasoning: str = ""

    def __post_init__(self) -> None:
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("执行计划包含重复任务 ID")

        agent_names = [task.agent_name for task in self.tasks]
        if len(agent_names) != len(set(agent_names)):
            raise ValueError("执行计划暂不支持重复调用同一 Agent")

        known_ids = set(task_ids)
        for task in self.tasks:
            missing = sorted(set(task.dependencies) - known_ids)
            if missing:
                raise ValueError(f"Agent 任务 {task.task_id!r} 依赖不存在的任务：{missing}")

        resolved: set[str] = set()
        remaining = {task.task_id: set(task.dependencies) for task in self.tasks}
        while remaining:
            ready = [
                task_id
                for task_id, dependencies in remaining.items()
                if dependencies <= resolved
            ]
            if not ready:
                raise ValueError("执行计划包含循环依赖")
            resolved.update(ready)
            for task_id in ready:
                remaining.pop(task_id)

    @property
    def agent_names(self) -> list[str]:
        return [task.agent_name for task in self.tasks]


@dataclass(frozen=True, slots=True)
class PlanIssue:
    task_id: str
    reason: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class PlanReview:
    issues: tuple[PlanIssue, ...] = ()
    retry_task_ids: tuple[str, ...] = ()

    @property
    def should_retry(self) -> bool:
        return bool(self.retry_task_ids)
