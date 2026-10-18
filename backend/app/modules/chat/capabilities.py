"""Chat Skill、Agent 与 Tool 能力目录应用服务。"""

from app.agentic.catalog import registry
from app.agentic_integration.agents.catalog import list_agent_profiles
from app.agentic_integration.bootstrap import register_all_capabilities
from app.configuration import get_effective_settings
from app.modules.chat.availability import build_capability_availability
from app.modules.chat.schemas import (
    ChatAgentCapabilityInfo,
    ChatCapabilitiesResponse,
    ChatCapabilityAvailabilityResponse,
    ChatSkillCapabilityInfo,
    ChatToolCapabilityInfo,
    ChatToolPolicyInfo,
)


def build_chat_capabilities() -> ChatCapabilitiesResponse:
    register_all_capabilities()
    skills = registry.list_skills()
    tool_to_skills: dict[str, list[str]] = {}
    for skill in skills:
        for tool_name in skill.tool_names:
            tool_to_skills.setdefault(tool_name, []).append(skill.name)

    return ChatCapabilitiesResponse(
        skills=[
            ChatSkillCapabilityInfo(
                name=skill.name,
                description=skill.description,
                triggers=list(skill.triggers),
                tool_names=list(skill.tool_names),
                rules=list(skill.rules),
                exclusions=list(skill.exclusions),
                priority=skill.priority,
            )
            for skill in skills
        ],
        agents=[
            ChatAgentCapabilityInfo(
                name=profile.name,
                display_name=profile.display_name,
                description=profile.description,
                tool_names=list(profile.tool_names),
                skill_names=list(profile.skill_names),
                max_rounds=profile.max_rounds,
            )
            for profile in list_agent_profiles()
        ],
        tools=[
            ChatToolCapabilityInfo(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                policy=ChatToolPolicyInfo(
                    cost=tool.policy.cost,
                    cache_ttl_seconds=tool.policy.cache_ttl_seconds,
                    freshness=tool.policy.freshness,
                    scope=tool.policy.scope,
                    timeout_seconds=tool.policy.timeout_seconds,
                    max_parallel_calls=tool.policy.max_parallel_calls,
                    max_result_characters=tool.policy.max_result_characters,
                ),
                skill_names=tool_to_skills.get(tool.name, []),
            )
            for tool in registry.list_tools()
        ],
        unassigned_tools=registry.validate_skill_coverage(),
    )


def load_chat_capability_availability() -> ChatCapabilityAvailabilityResponse:
    return build_capability_availability(get_effective_settings())
