"""系统级 HTTP 响应模型。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class VersionCheckResponse(BaseModel):
    current_version: str
    latest_version: str | None = None
    update_available: bool = False


class ReadinessResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["connected", "error"]
    config_encryption: str
    background_tasks: dict[str, dict[str, Any]]


class ProviderCircuitStateResponse(BaseModel):
    status: Literal["closed", "open", "half_open_ready", "half_open"]
    consecutive_failures: int = Field(ge=0)
    retry_in_seconds: float = Field(ge=0)


class HealthMetricsResponse(BaseModel):
    status: Literal["ok"]
    metrics: dict[str, Any]
    global_cache: dict[str, int]
    market_cache: dict[str, int]
    reference_cache: dict[str, int]
    analysis_cache: dict[str, int]
    series_cache: dict[str, int]
    provider_circuits: dict[str, ProviderCircuitStateResponse]


class DeleteResponse(BaseModel):
    deleted: bool = True


class WorkflowJobResponse(BaseModel):
    id: str
    kind: Literal["analysis", "industry_chain", "screener_strategy", "daily_review"]
    dedupe_key: str
    request: dict[str, Any]
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: float
    updated_at: float
    completed_at: float | None


class WorkflowSubmissionResponse(BaseModel):
    job: WorkflowJobResponse
    attached: bool
