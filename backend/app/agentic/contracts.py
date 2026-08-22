from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from app.agentic.tools.serialization import has_meaningful_tool_content

MAX_AGENT_SUMMARY_LENGTH = 12_000
MAX_EVIDENCE_ARGUMENT_LENGTH = 4_000
MAX_EVIDENCE_ITEM_LENGTH = 10_000
MAX_EVIDENCE_CONTEXT_LENGTH = 60_000


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    label: str
    tool_names: tuple[str, ...]
    validator: Callable[[AgentEvidence], bool] | None = None

    def accepts(self, evidence: AgentEvidence) -> bool:
        if (
            evidence.is_error
            or
            evidence.tool_name not in self.tool_names
            or not has_meaningful_tool_content(evidence.content)
        ):
            return False
        return self.validator(evidence) if self.validator is not None else True


@dataclass(frozen=True)
class AgentResearchSpec:
    name: str
    display_name: str
    system_prompt: str
    tool_names: tuple[str, ...]
    requirements: tuple[EvidenceRequirement, ...]
    max_rounds: int = 4

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.display_name.strip() or not self.system_prompt.strip():
            raise ValueError("Research Agent 缺少名称、展示名或 system prompt")
        if self.max_rounds < 1:
            raise ValueError("Research Agent max_rounds 必须大于 0")
        if len(self.tool_names) != len(set(self.tool_names)):
            raise ValueError("Research Agent 包含重复工具")
        requirement_keys = [requirement.key for requirement in self.requirements]
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("Research Agent 包含重复证据要求")
        unknown_tools = {
            tool_name
            for requirement in self.requirements
            for tool_name in requirement.tool_names
            if tool_name not in self.tool_names
        }
        if unknown_tools:
            raise ValueError(f"Research Agent 证据要求引用未知工具：{sorted(unknown_tools)}")


@dataclass(frozen=True)
class AgentEvidence:
    tool_call_id: str
    tool_name: str
    arguments: str
    content: str
    is_error: bool = False


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


def agent_evidence_id(evidence: AgentEvidence) -> str:
    try:
        arguments = json.dumps(
            json.loads(evidence.arguments),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        arguments = evidence.arguments.strip()
    digest = hashlib.sha256(
        f"{evidence.tool_name}\n{arguments}\n{evidence.is_error}\n{evidence.content}".encode("utf-8")
    ).hexdigest()[:16]
    return f"ev_{digest}"


def render_agent_evidence(
    evidence: tuple[AgentEvidence, ...] | list[AgentEvidence],
    *,
    max_context_length: int = MAX_EVIDENCE_CONTEXT_LENGTH,
    max_item_length: int = MAX_EVIDENCE_ITEM_LENGTH,
) -> str:
    sections: list[str] = []
    total_length = 0
    successful_evidence = [item for item in evidence if not item.is_error]
    for index, item in enumerate(successful_evidence, start=1):
        evidence_id = agent_evidence_id(item)
        payload = json.dumps(
            {
                "evidence_id": evidence_id,
                "tool_name": item.tool_name,
                "arguments": item.arguments[:MAX_EVIDENCE_ARGUMENT_LENGTH],
                "content": item.content[:max_item_length],
            },
            ensure_ascii=False,
        )
        section = (
            f'<tool_evidence id="{evidence_id}" index="{index}" '
            f'name="{item.tool_name}">{payload}</tool_evidence>'
        )
        if total_length + len(section) > max_context_length:
            break
        sections.append(section)
        total_length += len(section) + 1
    return "\n".join(sections) or "暂无可用工具证据"
