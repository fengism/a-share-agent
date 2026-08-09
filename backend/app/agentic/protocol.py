"""Agentic 消息与工具调用协议。"""

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
