from __future__ import annotations

from collections.abc import AsyncGenerator

from app.agentic.agents.catalog import list_agent_profiles
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.configuration import get_effective_settings
from app.core.metrics import metrics
from app.modules.chat.capability_plan import build_chat_capability_plan
from app.modules.chat.general_agent import stream_general_agent
from app.modules.chat.orchestrator import Orchestrator
from app.modules.chat.routing import RoutingDecision


async def run_chat_agent(
    message: str,
    history: list[AgentMessage] | None = None,
    agent_names: list[str] | None = None,
    skill_names: list[str] | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    """根据配置分派到多 Agent 编排器或传统单 Agent 循环。"""
    register_all_capabilities()
    settings = get_effective_settings()
    disabled_skills = set(settings.disabled_chat_skills)
    enabled_skill_names = [
        skill.name
        for skill in registry.list_skills()
        if skill.name not in disabled_skills
    ]
    if skill_names is not None:
        requested_skills = set(skill_names)
        enabled_skill_names = [
            name for name in enabled_skill_names if name in requested_skills
        ]
    disabled_agents = set(settings.disabled_chat_agents)
    enabled_agent_names = [
        profile.name
        for profile in list_agent_profiles()
        if profile.name not in disabled_agents
    ]
    if agent_names is not None:
        requested_agents = set(agent_names)
        enabled_agent_names = [
            name for name in enabled_agent_names if name in requested_agents
        ]
    plan = build_chat_capability_plan(
        message,
        enabled_skill_names=enabled_skill_names,
        enabled_agent_names=enabled_agent_names,
    )
    metrics.record_agentic_event("capability_plan")
    execution_context = AgentExecutionContext.from_current(
        settings,
        total_timeout_seconds=settings.chat_total_timeout_seconds,
    )
    if settings.multi_agent_enabled and plan.candidate_agent_names:
        orchestrator = Orchestrator(
            agent_names=plan.candidate_agent_names,
            skill_names=plan.active_skill_names,
            allowed_tool_names=plan.tool_names,
            require_tool_evidence=plan.requires_tool_evidence,
            execution_context=execution_context,
        )
        decision = RoutingDecision(
            agents=list(plan.candidate_agent_names),
            needs_llm_classification=plan.needs_llm_classification,
            reasoning=plan.reasoning,
        )
        async for delta in orchestrator.run(message, history, initial_decision=decision):
            yield delta
        return

    async for delta in stream_general_agent(
        message,
        history,
        tool_names=plan.tool_names,
        skill_names=plan.active_skill_names,
        require_tool_evidence=plan.requires_tool_evidence,
        execution_context=execution_context,
    ):
        yield delta
