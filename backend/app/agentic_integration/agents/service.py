from __future__ import annotations

from collections.abc import AsyncGenerator, Collection
from contextlib import aclosing
from typing import Any

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import agent_executor
from app.agentic.events import AgentEvent
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import (
    AgentExecutionContext,
    configure_request_context_provider,
)
from app.agentic.runtime.llm import configure_llm_transport
from app.agentic.runtime.metrics import configure_metrics
from app.agentic.runtime.settings import configure_default_settings
from app.configuration import get_effective_settings, get_settings
from app.core.metrics import metrics
from app.core.request_context import get_current_request_id, get_current_user_id
from app.infrastructure.llm.completion import create_chat_completion, stream_chat_completion
from app.infrastructure.llm.runtime import borrow_async_openai_chat_runtime

# Composition-time wiring: the core runtime only knows ports.
configure_llm_transport(create_chat_completion, stream_chat_completion)
configure_default_settings(get_settings)
configure_metrics(metrics)
configure_request_context_provider(
    lambda: (get_current_user_id(), get_current_request_id())
)


async def stream_agent(
    profile: AgentProfile,
    message: str,
    history: list[AgentMessage] | None = None,
    *,
    allowed_tool_names: Collection[str] | None = None,
    tool_selection_prompt: str = "",
    max_history_messages: int = 10,
    require_tool_first_round: bool = False,
    require_tool_evidence: bool = False,
    execution_context: AgentExecutionContext | None = None,
    settings: Any = None,
    tool_call_reserve: int = 0,
    task_id: str | None = None,
    attempt: int = 1,
) -> AsyncGenerator[AgentEvent, None]:
    effective_settings = settings or get_effective_settings()
    effective_context = execution_context or AgentExecutionContext.from_current(
        effective_settings,
        user_id=get_current_user_id(),
        request_id=get_current_request_id(),
    )
    async with borrow_async_openai_chat_runtime(effective_settings) as runtime:
        async with aclosing(agent_executor.stream(
            profile,
            message,
            history,
            runtime.client,
            runtime.model,
            allowed_tool_names=allowed_tool_names,
            temperature=effective_settings.llm_temperature,
            tool_selection_prompt=tool_selection_prompt,
            max_history_messages=max_history_messages,
            require_tool_first_round=require_tool_first_round,
            require_tool_evidence=require_tool_evidence,
            execution_context=effective_context,
            tool_call_reserve=tool_call_reserve,
            task_id=task_id,
            attempt=attempt,
        )) as stream:
            async for event in stream:
                yield event
