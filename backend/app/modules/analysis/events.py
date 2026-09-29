from typing import Literal

from pydantic import BaseModel

from app.agentic.events import AgentEvent
from app.modules.analysis.models import AnalysisResult

ANALYSIS_STAGE_NAMES = {
    1: "Agent 调研与证据校验",
    2: "构造结构化请求",
    3: "AI 综合分析",
    4: "结果校验与数据时效",
    5: "报告归档与历史更新",
}


class AnalysisStage(BaseModel):
    stage: int
    name: str
    status: Literal["started", "completed", "failed"]
    detail: str | None = None
    duration_ms: int | None = None


class AnalysisProgress(BaseModel):
    type: Literal[
        "stage_started",
        "stage_completed",
        "stage_failed",
        "agent_event",
        "complete",
        "error",
        "cached",
    ]
    stage: AnalysisStage | None = None
    total_stages: int = len(ANALYSIS_STAGE_NAMES)
    agent_event: AgentEvent | None = None
    result: AnalysisResult | None = None
    error: str | None = None
