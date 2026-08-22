from typing import Literal

from pydantic import BaseModel, Field

from app.agentic.protocol import ToolCallInfo, ToolResultInfo

AgentPlanStepStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
AgentExecutionStatus = Literal["completed", "partial", "failed"]


class AgentPlanStep(BaseModel):
    id: str
    title: str
    description: str | None = None
    agent_name: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    status: AgentPlanStepStatus = "pending"
    detail: str | None = None
    attempt: int = Field(default=0, ge=0)


class AgentPlan(BaseModel):
    summary: str | None = None
    steps: list[AgentPlanStep] = Field(default_factory=list)


class AgentPlanStepUpdate(BaseModel):
    step_id: str
    status: AgentPlanStepStatus
    detail: str | None = None
    attempt: int = Field(default=1, ge=1)


class AgentEvent(BaseModel):
    type: Literal[
        "status",
        "plan",
        "plan_step",
        "text",
        "reasoning",
        "tool_call",
        "tool_result",
        "error",
        "done",
    ]
    content: str | None = None
    plan: AgentPlan | None = None
    plan_step: AgentPlanStepUpdate | None = None
    tool_call: ToolCallInfo | None = None
    tool_result: ToolResultInfo | None = None
    error: str | None = None
    reasoning_content: str | None = None
    status: AgentExecutionStatus | None = None
    warnings: list[str] = Field(default_factory=list, max_length=16)
