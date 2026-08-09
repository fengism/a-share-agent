"""系统级 HTTP 响应模型。"""

from typing import Any, Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["connected", "error"]
    config_encryption: str
    background_tasks: dict[str, dict[str, Any]]


class HealthMetricsResponse(BaseModel):
    status: Literal["ok"]
    metrics: dict[str, Any]
    global_cache: dict[str, int]
    provider_circuits: dict[str, dict[str, Any]]
