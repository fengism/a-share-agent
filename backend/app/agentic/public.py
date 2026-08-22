"""Agentic 子系统对业务模块开放的稳定入口。"""

from collections.abc import Awaitable, Callable
from typing import Any, cast

from app.agentic.adapters.research import AgentExecutorResearchRuntime
from app.agentic.contracts import (
    AgentEvidence,
    AgentEvidenceInsufficientError,
    AgenticResearchResult,
    AgentResearchSpec,
    AgentRoundResult,
    EvidenceRequirement,
    agent_evidence_id,
)
from app.agentic.events import AgentEvent
from app.agentic.research import (
    AgentResearchRuntime,
    AgentResearchSession,
)
from app.agentic.research import run_agentic_research as _run_agentic_research
from app.agentic.tools.packs.web.search import execute_web_search

_DEFAULT_RUNTIME = AgentExecutorResearchRuntime()


async def run_agentic_research(
    spec: AgentResearchSpec,
    message: str,
    settings: Any = None,
    runtime: AgentResearchRuntime | None = None,
    event_callback: Callable[[AgentEvent], Awaitable[None]] | None = None,
) -> AgenticResearchResult:
    return cast(AgenticResearchResult, await _run_agentic_research(
        spec,
        message,
        runtime=runtime or _DEFAULT_RUNTIME,
        settings=settings,
        event_callback=event_callback,
    ))


__all__ = [
    "AgentEvidence",
    "AgentEvidenceInsufficientError",
    "AgenticResearchResult",
    "AgentResearchRuntime",
    "AgentResearchSession",
    "AgentResearchSpec",
    "AgentRoundResult",
    "EvidenceRequirement",
    "execute_web_search",
    "run_agentic_research",
    "agent_evidence_id",
]
