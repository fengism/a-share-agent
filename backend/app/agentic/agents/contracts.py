from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agentic.semantics import EvidenceState, ExecutionOutcome, ExecutionStatus, result_status, stop_reason

if TYPE_CHECKING:
    from app.agentic.orchestration.opinions import AgentOpinion


@dataclass(frozen=True, slots=True)
class AgentProfile:
    name: str
    display_name: str
    description: str
    system_prompt: str
    tool_names: tuple[str, ...]
    skill_names: tuple[str, ...] = ()
    max_rounds: int = 3

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", self.name) is None:
            raise ValueError(f"Agent 名称不合法：{self.name!r}")
        if not self.display_name.strip() or not self.description.strip():
            raise ValueError(f"Agent '{self.name}' 缺少展示信息")
        if not self.system_prompt.strip():
            raise ValueError(f"Agent '{self.name}' 缺少 system prompt")
        if len(self.tool_names) != len(set(self.tool_names)):
            raise ValueError(f"Agent '{self.name}' 包含重复工具")
        if len(self.skill_names) != len(set(self.skill_names)):
            raise ValueError(f"Agent '{self.name}' 包含重复 Skill")
        if self.max_rounds < 1:
            raise ValueError(f"Agent '{self.name}' max_rounds 必须大于 0")


@dataclass(frozen=True, slots=True)
class ToolExecutionSummary:
    name: str
    is_error: bool
    has_evidence: bool = False  # Raw acquisition succeeded with meaningful data.
    context_has_evidence: bool = False  # Evidence actually included in model context.
    # 未真实执行（预算拒绝、批内去重）。必须与「成功但没取到东西」区分开：否则
    # Reviewer 的 any(not is_error) / all(is_error) 两个判定都看不到它，一次零有效
    # 证据的任务会被当成 usable 注入下游。
    skipped: bool = False
    instruction: bool = False  # Control/instruction result, not data evidence.
    failure_code: str = ""  # Allowlisted category only; no raw provider details.

    @property
    def evidence_state(self) -> EvidenceState:
        return EvidenceState(self.has_evidence, self.context_has_evidence, self.is_error, self.skipped)


@dataclass(slots=True)
class AgentExecutionResult:
    agent_name: str
    display_name: str
    analysis: str
    status: ExecutionStatus = "completed"
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[ToolExecutionSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0
    reasoning_content: str = ""
    opinion: "AgentOpinion | None" = None
    retryable: bool = True
    termination_reason: str = ""  # Sanitized code, never a provider error body.

    @property
    def has_context_evidence(self) -> bool:
        return any(item.evidence_state.usable_context for item in self.tool_results)

    @property
    def outcome(self) -> ExecutionOutcome:
        reason = stop_reason(self.termination_reason)
        has_output = bool(self.analysis.strip())
        status = result_status(
            has_output=has_output,
            failed=self.status == "failed" or reason.fatal,
            incomplete=self.status == "partial" or reason.retain_acquired_evidence or bool(self.errors or self.warnings),
        )
        return ExecutionOutcome(
            status, reason, has_output,
            any(item.evidence_state.usable_acquisition for item in self.tool_results),
        )
