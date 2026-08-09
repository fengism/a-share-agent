from typing import Literal

from pydantic import BaseModel

from app.agentic.events import AgentEvent
from app.modules.industry_chain.models import IndustryChainResult


class IndustryChainProgress(BaseModel):
    type: Literal["stage_started", "stage_completed", "agent_event", "complete", "error"]
    stage: str = ""
    message: str = ""
    agent_event: AgentEvent | None = None
    result: IndustryChainResult | None = None
