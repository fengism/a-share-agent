"""Settings 模块的 API 契约。

配置字段与派生集合的唯一事实来源是 :mod:`app.configuration.api_models`，
这里只做转发并补充与本模块相关的请求/响应模型，避免重复维护字段清单。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.configuration.api_models import (
    CONFIG_VALUE_FIELDS,
    ConfigResponse,
    ConfigUpdateRequest,
)

__all__ = [
    "CONFIG_VALUE_FIELDS",
    "ConfigResponse",
    "ConfigUpdateRequest",
    "LlmModelsRequest",
    "LlmModelsResponse",
]


class LlmModelsRequest(BaseModel):
    """按 Base URL + API Key 拉取 OpenAI 兼容 /models 列表的请求。"""

    base_url: str = ""
    api_key: str = ""
    api_mode: str = ""
    api_version: str = ""


class LlmModelsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)
