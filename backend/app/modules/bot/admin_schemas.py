"""Bot 管理端 HTTP 契约。"""

from typing import Literal

from pydantic import BaseModel

BotJobStatus = Literal["pending", "running", "succeeded", "failed"]


class BotAdminJobItem(BaseModel):
    id: str
    event_id: str
    platform: str
    request_user_id: str
    command_name: str
    status: BotJobStatus
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: float
    updated_at: float
    completed_at: float | None


class BotAdminJobsResponse(BaseModel):
    counts: dict[str, int]
    jobs: list[BotAdminJobItem]
