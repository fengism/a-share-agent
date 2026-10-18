"""工具调用协议：被 agentic 与 infrastructure 共同依赖的最小契约。

放在 domain 层是为了让基础设施（LLM 适配层）不必反向依赖 agentic 业务模块，
同时保留 pydantic 校验与长度上限。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MAX_AGENT_CONTENT_LENGTH = 100_000


class ToolCallFunction(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    arguments: str = Field(max_length=MAX_AGENT_CONTENT_LENGTH)


class ToolCallInfo(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    type: Literal["function"] = "function"
    function: ToolCallFunction
