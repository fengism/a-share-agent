"""Host-facing agentic entry points.

Core contracts stay in :mod:`app.agentic.public`; this module adds the default
research runtime and the web-search compatibility wrapper used by business code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

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
    AgentEventCallback,
    AgentResearchRuntime,
    AgentResearchSession,
)
from app.agentic.research import run_agentic_research as _run_agentic_research
from app.agentic.semantics import (
    EvidenceState,
    ExecutionOutcome,
    ExecutionStatus,
    StopReason,
    stop_reason,
)
from app.agentic_integration.adapters.research import AgentExecutorResearchRuntime
from app.agentic_integration.tools.packs.web.search import execute_web_search as _execute_web_search

_DEFAULT_RUNTIME = AgentExecutorResearchRuntime()


async def run_agentic_research(
    spec: AgentResearchSpec,
    message: str,
    settings: Any = None,
    runtime: AgentResearchRuntime | None = None,
    event_callback: Callable[[AgentEvent], Awaitable[None]] | None = None,
    evidence_callback: Callable[[AgentEvidence], None] | None = None,
    initial_evidence: Sequence[AgentEvidence] | None = None,
) -> AgenticResearchResult:
    return cast(AgenticResearchResult, await _run_agentic_research(
        spec,
        message,
        runtime=runtime or _DEFAULT_RUNTIME,
        settings=settings,
        event_callback=event_callback,
        evidence_callback=evidence_callback,
        initial_evidence=initial_evidence,
    ))


async def execute_web_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return cast(dict[str, Any], await _execute_web_search(*args, **kwargs))


__all__ = [
    "EvidenceState",
    "ExecutionOutcome",
    "ExecutionStatus",
    "StopReason",
    "stop_reason",
    "AgentEvidence",
    "AgentEvidenceInsufficientError",
    "AgentEvent",
    "AgentEventCallback",
    "AgenticResearchResult",
    "AgentResearchRuntime",
    "AgentResearchSession",
    "AgentResearchSpec",
    "AgentRoundResult",
    "EvidenceRequirement",
    "agent_evidence_id",
    "execute_web_search",
    "run_agentic_research",
]
