"""Agentic 消息与工具调用协议。"""

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.agent_protocol import (
    MAX_AGENT_CONTENT_LENGTH,
    ToolCallFunction,
    ToolCallInfo,
)

__all__ = [
    "MAX_AGENT_CONTENT_LENGTH",
    "AgentMessage",
    "ToolCallFunction",
    "ToolCallInfo",
    "ToolResultInfo",
]


class ToolResultInfo(BaseModel):
    tool_call_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    content: str = Field(max_length=MAX_AGENT_CONTENT_LENGTH)
    is_error: bool = False


class AgentMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str | None = Field(default=None, max_length=MAX_AGENT_CONTENT_LENGTH)
    tool_calls: list[ToolCallInfo] | None = Field(default=None, max_length=32)
    tool_call_id: str | None = Field(default=None, max_length=256)
    name: str | None = Field(default=None, max_length=128)
    reasoning_content: str | None = Field(default=None, max_length=MAX_AGENT_CONTENT_LENGTH)
