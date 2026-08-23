from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

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
    has_evidence: bool = False


@dataclass(slots=True)
class AgentExecutionResult:
    agent_name: str
    display_name: str
    analysis: str
    status: Literal["completed", "partial", "failed"] = "completed"
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[ToolExecutionSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0
    reasoning_content: str = ""
    opinion: "AgentOpinion | None" = None
