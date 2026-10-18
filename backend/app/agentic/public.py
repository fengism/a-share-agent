"""Agentic core public contracts (host-independent).

Host-facing helpers such as the default research runtime and web-search
compatibility wrapper live in :mod:`app.agentic_integration.public`.
"""

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
from app.agentic.semantics import (
    EvidenceState,
    ExecutionOutcome,
    ExecutionStatus,
    StopReason,
    stop_reason,
)

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
]
