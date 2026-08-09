from typing import Literal

from pydantic import BaseModel

from app.modules.analysis.models import AnalysisResult


class AnalysisStage(BaseModel):
    stage: int
    name: str
    status: Literal["started", "completed", "failed"]
    detail: str | None = None
    duration_ms: int | None = None


class AnalysisProgress(BaseModel):
    type: Literal["stage_started", "stage_completed", "stage_failed", "complete", "error", "cached"]
    stage: AnalysisStage | None = None
    total_stages: int = 3
    result: AnalysisResult | None = None
    error: str | None = None
