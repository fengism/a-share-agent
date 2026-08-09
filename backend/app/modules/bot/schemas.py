"""Bot Webhook HTTP 契约。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeishuWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_: str | None = Field(default=None, alias="schema")
    type: str | None = None
    token: str | None = None
    challenge: str | None = None
    encrypt: str | None = None
    header: dict[str, Any] | None = None
    event: dict[str, Any] | None = None


class FeishuWebhookResponse(BaseModel):
    challenge: str | None = None
    code: int | None = None
