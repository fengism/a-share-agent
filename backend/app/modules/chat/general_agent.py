from __future__ import annotations

from collections.abc import AsyncGenerator, Collection
from contextlib import aclosing

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.service import stream_agent
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.modules.chat.prompts import SYSTEM_PROMPT

_MAX_ROUNDS = 5
_MAX_HISTORY_MESSAGES = 20


async def stream_general_agent(
    message: str,
    history: list[AgentMessage] | None = None,
    *,
    tool_names: Collection[str] | None = None,
    skill_names: Collection[str] | None = None,
    require_tool_evidence: bool = False,
    execution_context: AgentExecutionContext | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    effective_tool_names = (
        tuple(tool.name for tool in registry.list_tools())
        if tool_names is None
        else tuple(dict.fromkeys(tool_names))
    )
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
        tool_selection_prompt=registry.get_skill_prompt(skill_names),
        max_history_messages=_MAX_HISTORY_MESSAGES,
        require_tool_first_round=require_tool_evidence,
        require_tool_evidence=require_tool_evidence,
        execution_context=execution_context,
    )) as stream:
        async for event in stream:
            yield event
