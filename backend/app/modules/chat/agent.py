from __future__ import annotations

from collections.abc import AsyncGenerator

from app.agentic.agents.catalog import list_agent_profiles
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.protocol import AgentMessage
from app.configuration import get_effective_settings
from app.modules.chat.general_agent import stream_general_agent
from app.modules.chat.orchestrator import Orchestrator


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
    tool_names = registry.get_tool_names_for_skills(enabled_skill_names)
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
    if settings.multi_agent_enabled and enabled_agent_names:
        orchestrator = Orchestrator(
            agent_names=enabled_agent_names,
            skill_names=enabled_skill_names,
            allowed_tool_names=tool_names,
        )
        async for delta in orchestrator.run(message, history):
            yield delta
        return

    async for delta in stream_general_agent(
        message,
        history,
        tool_names=tool_names,
        skill_names=enabled_skill_names,
    ):
        yield delta
