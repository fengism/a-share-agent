from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
from app.agentic.agents.executor import AgentExecutor, agent_executor
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.contracts import (
    MAX_EVIDENCE_ARGUMENT_LENGTH,
    MAX_EVIDENCE_ITEM_LENGTH,
    AgentEvidence,
    AgentResearchSpec,
    AgentRoundResult,
)
from app.agentic.events import AgentEvent
from app.agentic.research import AgentEventCallback, build_research_system_prompt
from app.infrastructure.llm.runtime import borrow_async_openai_chat_runtime


def _collect_round_evidence(events: list[AgentEvent]) -> tuple[AgentEvidence, ...]:
    calls: dict[str, tuple[str, str]] = {}
    evidence: list[AgentEvidence] = []
    for delta in events:
        if delta.type == "tool_call" and delta.tool_call is not None:
            calls[delta.tool_call.id] = (
                delta.tool_call.function.name,
                delta.tool_call.function.arguments,
            )
        elif delta.type == "tool_result" and delta.tool_result is not None and not delta.tool_result.is_error:
            tool_name, arguments = calls.get(
                delta.tool_result.tool_call_id,
                (delta.tool_result.name, "{}"),
            )
            evidence.append(AgentEvidence(
                tool_call_id=delta.tool_result.tool_call_id,
                tool_name=tool_name,
                arguments=arguments[:MAX_EVIDENCE_ARGUMENT_LENGTH],
                content=delta.tool_result.content[:MAX_EVIDENCE_ITEM_LENGTH],
            ))
    return tuple(evidence)


@dataclass(frozen=True)
class _ResearchExecutionCompleted:
    result: AgentExecutionResult


@dataclass(frozen=True)
class _ResearchExecutionFailed:
    error: BaseException


@dataclass
class _AgentExecutorResearchSession:
    profile: AgentProfile
    executor: AgentExecutor
    client: Any
    model: str
    temperature: float

    async def run(
        self,
        message: str,
        allowed_tool_names: tuple[str, ...],
        event_callback: AgentEventCallback | None = None,
    ) -> AgentRoundResult:
        event_queue: asyncio.Queue[
            AgentEvent | _ResearchExecutionCompleted | _ResearchExecutionFailed
        ] = asyncio.Queue()
        events: list[AgentEvent] = []

        async def execute() -> None:
            try:
                result = await self.executor.run(
                    self.profile,
                    message,
                    None,
                    self.client,
                    self.model,
                    event_queue=event_queue,
                    allowed_tool_names=allowed_tool_names,
                    temperature=self.temperature,
                )
                await event_queue.put(_ResearchExecutionCompleted(result))
            except BaseException as error:
                await event_queue.put(_ResearchExecutionFailed(error))

        execution_task = asyncio.create_task(execute())
        try:
            while True:
                event = await event_queue.get()
                if isinstance(event, _ResearchExecutionFailed):
                    raise event.error
                if isinstance(event, _ResearchExecutionCompleted):
                    result = event.result
                    break
                events.append(event)
                if event_callback is not None:
                    await event_callback(event)
        finally:
            if not execution_task.done():
                execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)

        return AgentRoundResult(
            summary=result.analysis.strip(),
            evidence=_collect_round_evidence(events),
        )


class AgentExecutorResearchRuntime:
    @asynccontextmanager
    async def open_session(
        self,
        spec: AgentResearchSpec,
        settings: Any = None,
    ) -> AsyncIterator[_AgentExecutorResearchSession]:
        register_all_capabilities()
        profile = AgentProfile(
            name=spec.name,
            display_name=spec.display_name,
            description=spec.display_name,
            system_prompt=build_research_system_prompt(spec),
            tool_names=spec.tool_names,
            max_rounds=spec.max_rounds,
        )
        temperature = getattr(settings, "llm_temperature", 0.1)
        async with borrow_async_openai_chat_runtime(settings) as runtime:
            yield _AgentExecutorResearchSession(
                profile=profile,
                executor=agent_executor,
                client=runtime.client,
                model=runtime.model,
                temperature=temperature,
            )
