from __future__ import annotations

from collections.abc import Collection, Mapping

from app.agentic.orchestration.contracts import (
    AgentDescriptor,
    AgentTask,
    ExecutionPlan,
)

DEFAULT_AGENT_DEPENDENCIES: Mapping[str, tuple[str, ...]] = {
    "risk": ("fundamental", "technical"),
}


def build_execution_plan(
    agent_names: Collection[str],
    available_agents: Mapping[str, AgentDescriptor],
    allowed_tool_names: Collection[str] | None = None,
    *,
    reasoning: str = "",
    enable_dag: bool = True,
    custom_dependencies: Mapping[str, tuple[str, ...]] | None = None,
) -> ExecutionPlan:
    tasks: list[AgentTask] = []
    selected: set[str] = set()
    allowed_tools = None if allowed_tool_names is None else set(allowed_tool_names)
    agent_names_set = set(agent_names)
    deps_map = custom_dependencies if custom_dependencies is not None else DEFAULT_AGENT_DEPENDENCIES

    for agent_name in agent_names:
        if agent_name in selected:
            continue
        agent = available_agents.get(agent_name)
        if agent is None:
            continue
        selected.add(agent_name)

        candidate_deps = deps_map.get(agent_name, ()) if enable_dag else ()
        valid_dependencies = tuple(
            dep for dep in candidate_deps if dep in agent_names_set and dep != agent_name
        )

        tasks.append(
            AgentTask(
                task_id=agent_name,
                agent_name=agent_name,
                display_name=agent.display_name,
                objective=getattr(agent, "description", "") or f"完成{agent.display_name}任务",
                dependencies=valid_dependencies,
                allowed_tools=tuple(
                    tool_name
                    for tool_name in agent.tool_names
                    if allowed_tools is None or tool_name in allowed_tools
                ),
            )
        )

    return ExecutionPlan(
        tasks=tuple(tasks),
        reasoning=reasoning,
    )
