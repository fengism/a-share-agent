from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

MAX_AGENT_SUMMARY_LENGTH = 12_000
MAX_EVIDENCE_ARGUMENT_LENGTH = 4_000
MAX_EVIDENCE_ITEM_LENGTH = 10_000
MAX_EVIDENCE_CONTEXT_LENGTH = 60_000


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    label: str
    tool_names: tuple[str, ...]


@dataclass(frozen=True)
class AgentResearchSpec:
    name: str
    display_name: str
    system_prompt: str
    tool_names: tuple[str, ...]
    requirements: tuple[EvidenceRequirement, ...]
    max_rounds: int = 4


@dataclass(frozen=True)
class AgentEvidence:
    tool_call_id: str
    tool_name: str
    arguments: str
    content: str


@dataclass(frozen=True)
class AgentRoundResult:
    summary: str
    evidence: tuple[AgentEvidence, ...] = ()


@dataclass(frozen=True)
class AgenticResearchResult:
    summary: str
    evidence: tuple[AgentEvidence, ...]

    def render_prompt_context(self) -> dict[str, str]:
        return {
            "agent_summary": self.summary[:MAX_AGENT_SUMMARY_LENGTH],
            "agent_evidence": render_agent_evidence(self.evidence),
        }

    def as_tool_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary[:MAX_AGENT_SUMMARY_LENGTH],
            "evidence": [asdict(item) for item in self.evidence],
        }


class AgentEvidenceInsufficientError(RuntimeError):
    pass


def render_agent_evidence(
    evidence: tuple[AgentEvidence, ...] | list[AgentEvidence],
) -> str:
    sections: list[str] = []
    total_length = 0
    for index, item in enumerate(evidence, start=1):
        payload = json.dumps(
            {
                "tool_name": item.tool_name,
                "arguments": item.arguments[:MAX_EVIDENCE_ARGUMENT_LENGTH],
                "content": item.content[:MAX_EVIDENCE_ITEM_LENGTH],
            },
            ensure_ascii=False,
        )
        section = f'<tool_evidence index="{index}" name="{item.tool_name}">{payload}</tool_evidence>'
        if total_length + len(section) > MAX_EVIDENCE_CONTEXT_LENGTH:
            break
        sections.append(section)
        total_length += len(section) + 1
    return "\n".join(sections) or "暂无可用工具证据"
