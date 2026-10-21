from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from functools import cached_property
from typing import Any

from app.agentic.events import AgentEvent
from app.agentic.semantics import EvidenceState, ExecutionOutcome, ExecutionStatus, research_outcome
from app.agentic.tools.serialization import serialize_context_result

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
    fatal: bool = True

    def accepts(self, evidence: AgentEvidence) -> bool:
        if (
            evidence.tool_name not in self.tool_names
            or not evidence.evidence_state.usable_acquisition
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
    # Outer evidence-gap rounds and inner LLM/tool turns are different budgets.
    # None preserves existing callers' turn limit.
    max_tool_turns: int | None = None
    allow_incomplete_summary: bool = False
    reserved_tool_names: tuple[str, ...] = ()
    reserved_tool_calls: int = 0
    search_tool_names: tuple[str, ...] = ()
    search_total_limit: int = 0
    search_burst_limit: int = 0
    document_search_guidance: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.display_name.strip() or not self.system_prompt.strip():
            raise ValueError("Research Agent 缺少名称、展示名或 system prompt")
        if self.max_rounds < 1:
            raise ValueError("Research Agent max_rounds 必须大于 0")
        if self.max_tool_turns is not None and self.max_tool_turns < 1:
            raise ValueError("Research Agent max_tool_turns 必须大于 0")
        if len(self.tool_names) != len(set(self.tool_names)):
            raise ValueError("Research Agent 包含重复工具")
        requirement_keys = [requirement.key for requirement in self.requirements]
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("Research Agent 包含重复证据要求")
        if self.reserved_tool_calls < 0 or not set(self.reserved_tool_names) <= set(self.tool_names):
            raise ValueError("Research Agent 正文预留额度或工具无效")
        if self.search_tool_names and (
            not set(self.search_tool_names) <= set(self.tool_names)
            or not 1 <= self.search_burst_limit <= self.search_total_limit
            or not self.reserved_tool_names
            or set(self.search_tool_names) & set(self.reserved_tool_names)
        ):
            raise ValueError("Research Agent 搜索/正文节奏配置无效")
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

    @cached_property
    def evidence_state(self) -> EvidenceState:
        return EvidenceState.from_content(self.content, is_error=self.is_error)

    @cached_property
    def evidence_id(self) -> str:
        """Stable content identity, cached because evidence is immutable."""
        return _agent_evidence_id(self)


@dataclass(frozen=True)
class AgentRoundResult:
    summary: str
    evidence: tuple[AgentEvidence, ...] = ()
    stop_reason: str = ""  # Incomplete summary: retain tools, do not run more research rounds.
    tool_calls_remaining: int | None = None
    termination_reason: str = ""  # Machine code; stop_reason remains existing human-readable text.
    execution_status: ExecutionStatus | None = None

    @property
    def outcome(self) -> ExecutionOutcome:
        evidence = any(item.evidence_state.usable_acquisition for item in self.evidence)
        return research_outcome(
            summary=self.summary, has_evidence=evidence, termination_reason=self.termination_reason,
            execution_status=self.execution_status, incomplete=bool(self.stop_reason),
        )


@dataclass(frozen=True)
class AgenticResearchResult:
    summary: str
    evidence: tuple[AgentEvidence, ...]
    evidence_gaps: tuple[str, ...] = ()
    execution_trace: tuple[AgentEvent, ...] = ()
    stopped_early: bool = False
    termination_reason: str = ""
    execution_status: ExecutionStatus | None = None

    @property
    def outcome(self) -> ExecutionOutcome:
        evidence = any(item.evidence_state.usable_acquisition for item in self.evidence)
        return research_outcome(
            summary=self.summary, has_evidence=evidence, termination_reason=self.termination_reason,
            execution_status=self.execution_status, incomplete=bool(self.evidence_gaps or self.stopped_early),
        )

    def render_prompt_context(self) -> dict[str, Any]:
        return {
            "agent_summary": self.summary[:MAX_AGENT_SUMMARY_LENGTH],
            "agent_evidence": render_agent_evidence(self.evidence),
            "agent_evidence_gaps": "、".join(self.evidence_gaps) or "无",
            "agent_evidence_gap_labels": self.evidence_gaps,
        }

    def as_tool_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary[:MAX_AGENT_SUMMARY_LENGTH],
            "evidence": [asdict(item) for item in self.evidence],
            "evidence_gaps": list(self.evidence_gaps),
            "execution_trace": [item.model_dump(mode="json") for item in self.execution_trace],
        }


class AgentEvidenceInsufficientError(RuntimeError):
    """调研证据不足。

    必须携带本轮已采集的证据：抛异常时把 ``evidence`` 一起丢掉，pipeline 只能退化成
    一句硬编码文案 + 公共数据继续合成，等于把已经读到的正文/财报全部作废。
    """

    def __init__(
        self,
        message: str,
        *,
        summary: str = "",
        evidence: tuple[AgentEvidence, ...] | list[AgentEvidence] = (),
    ) -> None:
        super().__init__(message)
        self.summary = summary
        self.evidence: tuple[AgentEvidence, ...] = tuple(evidence)


# 每次调用都会变的字段：参与内容指纹的话，同一 URL 在主调研与补证阶段各读一次就会
# 得到两个 evidence_id —— 去重永久失效，重读被计成「新增证据」。
_VOLATILE_CONTENT_KEYS = frozenset(
    {
        "fetched_at",
        "retrieved_at",
        "generated_at",
        "created_at",
        "cached_at",
        "elapsed_ms",
        "elapsed_seconds",
        "duration_ms",
    }
)


def _strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_volatile(item)
            for key, item in value.items()
            if key not in _VOLATILE_CONTENT_KEYS
        }
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value


def _content_fingerprint(content: str) -> str:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return content
    return json.dumps(_strip_volatile(payload), ensure_ascii=False, sort_keys=True, default=str)


def _agent_evidence_id(evidence: AgentEvidence) -> str:
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
        (
            f"{evidence.tool_name}\n{arguments}\n{evidence.is_error}\n"
            f"{_content_fingerprint(evidence.content)}"
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"ev_{digest}"


def agent_evidence_id(evidence: AgentEvidence) -> str:
    """Return the cached evidence identity without re-hashing large payloads."""
    return evidence.evidence_id


@dataclass(frozen=True)
class EvidenceBatchStats:
    """Counts for collected evidence records, not calls, sources or verified claims."""

    added: tuple[AgentEvidence, ...]
    duplicate_count: int = 0
    failed_count: int = 0
    unusable_count: int = 0


def classify_evidence_batch(
    evidence: Iterable[AgentEvidence], *, seen_ids: set[str] | None = None,
) -> EvidenceBatchStats:
    seen = set() if seen_ids is None else seen_ids
    added: list[AgentEvidence] = []
    duplicates = failed = unusable = 0
    for item in evidence:
        if item.is_error:
            failed += 1
        elif not item.evidence_state.usable_acquisition:
            unusable += 1
        else:
            identity = agent_evidence_id(item)
            if identity in seen:
                duplicates += 1
            else:
                seen.add(identity)
                added.append(item)
    return EvidenceBatchStats(tuple(added), duplicates, failed, unusable)


def render_agent_evidence(
    evidence: tuple[AgentEvidence, ...] | list[AgentEvidence],
    *,
    max_context_length: int = MAX_EVIDENCE_CONTEXT_LENGTH,
    max_item_length: int = MAX_EVIDENCE_ITEM_LENGTH,
) -> str:
    sections: list[str] = []
    total_length = 0
    successful_evidence = classify_evidence_batch(evidence).added
    for index, item in enumerate(successful_evidence, start=1):
        evidence_id = agent_evidence_id(item)
        payload = json.dumps(
            {
                "evidence_id": evidence_id,
                "tool_name": item.tool_name,
                "arguments": item.arguments[:MAX_EVIDENCE_ARGUMENT_LENGTH],
                "content": serialize_context_result(item.content, max_item_length),
            },
            ensure_ascii=False,
            separators=(",", ":"),
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
