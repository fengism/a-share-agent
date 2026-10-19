from __future__ import annotations

from collections.abc import AsyncGenerator, Collection
from contextlib import aclosing

from app.agentic.agents.contracts import AgentProfile
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic_integration.agents.service import stream_agent
from app.configuration import get_effective_settings
from app.core.metrics import metrics
from app.modules.chat.prompts import SYSTEM_PROMPT

_MAX_ROUNDS = 5
_MAX_HISTORY_MESSAGES = 20
_LOAD_SKILL_TOOL = "load_skill"


def _build_skill_prompt(
    skill_names: Collection[str] | None,
    execution_context: AgentExecutionContext | None,
    *,
    active_skill_names: Collection[str] | None = None,
) -> str:
    settings = (
        execution_context.settings
        if execution_context is not None
        else get_effective_settings()
    )
    top_n = int(getattr(settings, "chat_skill_instruction_top_n", 0))
    if top_n < 0:
        metrics.record_agentic_event("skill_prompt_mode_full")
        return registry.get_skill_prompt(skill_names)
    catalog = registry.get_skill_catalog_prompt(
        skill_names, active_skill_names=active_skill_names
    )
    if catalog:
        metrics.record_agentic_event("skill_catalog_injected")
        metrics.record_agentic_event(
            "skill_prompt_mode_catalog" if top_n == 0 else "skill_prompt_mode_top_n"
        )
    if catalog and top_n == 0 and registry.get_tool(_LOAD_SKILL_TOOL) is not None:
        catalog = (
            f"需要详细规则或更多工具时调用 {_LOAD_SKILL_TOOL}(name)。\n\n{catalog}"
        )
    instruction_skills = tuple(active_skill_names or ()) or skill_names
    instructions = (
        registry.get_skill_instructions(instruction_skills, limit=top_n)
        if top_n > 0
        else ""
    )
    if instructions:
        metrics.record_agentic_event("skill_instructions_injected")
    return "\n\n".join(part for part in (catalog, instructions) if part)


async def stream_general_agent(
    message: str,
    history: list[AgentMessage] | None = None,
    *,
    tool_names: Collection[str] | None = None,
    skill_names: Collection[str] | None = None,
    enabled_skill_names: Collection[str] | None = None,
    enabled_tool_names: Collection[str] | None = None,
    require_tool_evidence: bool = False,
    execution_context: AgentExecutionContext | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    settings = (
        execution_context.settings
        if execution_context is not None
        else get_effective_settings()
    )
    dynamic_activation = bool(
        getattr(settings, "chat_skill_dynamic_activation_enabled", True)
    )
    active_skills = tuple(skill_names or ())
    loadable_skills = (
        tuple(enabled_skill_names)
        if dynamic_activation and enabled_skill_names is not None
        else active_skills
    )
    effective_tool_names = (
        tuple(tool.name for tool in registry.list_tools())
        if tool_names is None
        else tuple(dict.fromkeys(tool_names))
    )
    expansion_tool_names = (
        tuple(enabled_tool_names)
        if dynamic_activation and enabled_tool_names is not None
        else tuple(effective_tool_names)
    )
    if loadable_skills and registry.get_tool(_LOAD_SKILL_TOOL) is not None:
        effective_tool_names = tuple(dict.fromkeys((*effective_tool_names, _LOAD_SKILL_TOOL)))
    if execution_context is not None:
        execution_context.allowed_skill_names = loadable_skills
        execution_context.enabled_tool_names = expansion_tool_names
        execution_context.active_skill_names = active_skills
    profile = AgentProfile(
        name="general-chat",
        display_name="A 股智能助手",
        description="处理通用对话和未命中专业路由的分析请求",
        system_prompt=SYSTEM_PROMPT,
        tool_names=effective_tool_names,
        max_rounds=_MAX_ROUNDS,
    )
    async with aclosing(stream_agent(
        profile,
        message,
        history,
        allowed_tool_names=effective_tool_names,
        tool_selection_prompt=_build_skill_prompt(
            loadable_skills, execution_context, active_skill_names=active_skills
        ),
        max_history_messages=_MAX_HISTORY_MESSAGES,
        require_tool_first_round=require_tool_evidence,
        require_tool_evidence=require_tool_evidence,
        execution_context=execution_context,
    )) as stream:
        async for event in stream:
            yield event
