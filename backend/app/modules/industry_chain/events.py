from typing import Literal

from pydantic import BaseModel, Field

from app.agentic.events import AgentEvent
from app.modules.industry_chain.models import IndustryChainResult


class IndustryChainProgress(BaseModel):
    type: Literal["stage_started", "stage_completed", "stage_failed", "agent_event", "complete", "error"]
    stage: str = ""
    message: str = ""
    agent_event: AgentEvent | None = None
    result: IndustryChainResult | None = None
    archive_id: str = ""
    archive_status: Literal["none", "saved", "failed"] = "none"
    quality_status: Literal["complete", "degraded"] = "complete"
    warnings: list[str] = Field(default_factory=list)
