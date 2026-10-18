from __future__ import annotations

from app.agentic.catalog import registry
from app.agentic_integration.agents.catalog import list_agent_profiles
from app.agentic_integration.bootstrap import register_all_capabilities
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings
from app.modules.chat.schemas import (
    ChatCapabilityAvailabilityInfo,
    ChatCapabilityAvailabilityResponse,
)

_IWENCAI_TOOL_NAMES = {
    "iwencai_search",
    "iwencai_query",
    "iwencai_select_stock",
    "iwencai_market_macro",
}


def _llm_availability(settings: Settings) -> ChatCapabilityAvailabilityInfo:
    provider = settings.llm_provider.lower()
    defaults = PROVIDER_DEFAULTS.get(provider)
    if defaults is None:
        return ChatCapabilityAvailabilityInfo(
            status="unavailable",
            reason=f"未知 LLM Provider: {settings.llm_provider}",
        )
    if defaults.get("api_key_required", True) and not settings.llm_api_key:
        return ChatCapabilityAvailabilityInfo(
            status="unavailable",
            reason=f"{defaults['label']} 缺少 API Key",
        )
    if not settings.llm_base_url or not settings.llm_model:
        return ChatCapabilityAvailabilityInfo(
            status="unavailable",
            reason="LLM Base URL 或 Model 未配置",
        )
    return ChatCapabilityAvailabilityInfo(
        status="ready",
        reason=f"{defaults['label']} 配置完整",
    )


def build_capability_availability(
    settings: Settings,
) -> ChatCapabilityAvailabilityResponse:
    register_all_capabilities()
    llm = _llm_availability(settings)
    disabled_skills = set(settings.disabled_chat_skills)
    disabled_agents = set(settings.disabled_chat_agents)
    iwencai_ready = bool(settings.iwencai_enabled and settings.iwencai_api_key)

    skill_availability: dict[str, ChatCapabilityAvailabilityInfo] = {}
    active_tool_names: set[str] = set()
    for skill in registry.list_skills():
        if skill.name in disabled_skills:
            skill_availability[skill.name] = ChatCapabilityAvailabilityInfo(
                status="disabled",
                reason="当前账号已关闭",
            )
            continue
        active_tool_names.update(skill.tool_names)
        if llm.status == "unavailable":
            skill_availability[skill.name] = ChatCapabilityAvailabilityInfo(
                status="unavailable",
                reason="LLM 配置不可用",
            )
            continue
        iwencai_tools = set(skill.tool_names) & _IWENCAI_TOOL_NAMES
        if iwencai_tools and not iwencai_ready:
            skill_availability[skill.name] = ChatCapabilityAvailabilityInfo(
                status="degraded",
                reason="问财未启用或缺少 API Key，相关工具不可用",
            )
            continue
        skill_availability[skill.name] = ChatCapabilityAvailabilityInfo(
            status="ready",
            reason="配置完整",
        )

    agent_availability: dict[str, ChatCapabilityAvailabilityInfo] = {}
    for profile in list_agent_profiles():
        if profile.name in disabled_agents:
            agent_availability[profile.name] = ChatCapabilityAvailabilityInfo(
                status="disabled",
                reason="当前账号已关闭",
            )
            continue
        if llm.status == "unavailable":
            agent_availability[profile.name] = ChatCapabilityAvailabilityInfo(
                status="unavailable",
                reason="LLM 配置不可用",
            )
            continue

        configured_tools = set(profile.tool_names) & active_tool_names
        ready_tools = configured_tools - (
            _IWENCAI_TOOL_NAMES if not iwencai_ready else set()
        )
        if not ready_tools:
            agent_availability[profile.name] = ChatCapabilityAvailabilityInfo(
                status="degraded",
                reason="没有可用工具，将仅基于对话上下文分析",
            )
        elif ready_tools != set(profile.tool_names):
            agent_availability[profile.name] = ChatCapabilityAvailabilityInfo(
                status="degraded",
                reason="部分 Skill 或数据源未启用",
            )
        else:
            agent_availability[profile.name] = ChatCapabilityAvailabilityInfo(
                status="ready",
                reason="配置完整",
            )

    return ChatCapabilityAvailabilityResponse(
        llm=llm,
        skills=skill_availability,
        agents=agent_availability,
    )
