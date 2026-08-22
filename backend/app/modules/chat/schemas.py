import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.agentic.protocol import AgentMessage

__all__ = [
    "ChatAgentCapabilityInfo",
    "ChatCapabilitiesResponse",
    "ChatCapabilityAvailabilityInfo",
    "ChatCapabilityAvailabilityResponse",
    "ChatRequest",
    "ChatSessionData",
    "ChatSessionMeta",
    "ChatStateResponse",
    "ChatStateSnapshot",
    "ChatSkillCapabilityInfo",
    "ChatToolCapabilityInfo",
    "ChatToolPolicyInfo",
]

MAX_CHAT_MESSAGE_LENGTH = 10_000
MAX_CHAT_HISTORY_MESSAGES = 100
MAX_CHAT_HISTORY_CHARACTERS = 100_000
MAX_CHAT_STATE_CHARACTERS = 1_000_000


class ChatRequest(BaseModel):
    """Purpose: 聊天接口的请求体。"""
    message: str = Field(min_length=1, max_length=MAX_CHAT_MESSAGE_LENGTH)
    history: list[AgentMessage] | None = Field(default=None, max_length=MAX_CHAT_HISTORY_MESSAGES)
    agent_names: list[str] | None = Field(default=None, max_length=16)
    skill_names: list[str] | None = Field(default=None, max_length=32)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("消息不能为空")
        return message

    @field_validator("agent_names", "skill_names")
    @classmethod
    def validate_capability_names(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if any(re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name) is None for name in value):
            raise ValueError("能力名称格式不合法")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_total_history_size(self) -> "ChatRequest":
        total = len(self.message)
        for item in self.history or []:
            total += len(item.content or "")
            total += len(item.reasoning_content or "")
            total += sum(len(tool.function.arguments) for tool in item.tool_calls or [])
            if total > MAX_CHAT_HISTORY_CHARACTERS:
                raise ValueError("对话历史过长，请新建会话后继续")
        return self


class ChatSessionMeta(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    created_at: int = Field(ge=0)
    updated_at: int = Field(ge=0)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()


class ChatSessionData(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    history: list[AgentMessage] = Field(default_factory=list, max_length=MAX_CHAT_HISTORY_MESSAGES)
    agent_names: list[str] | None = Field(default=None, max_length=16)
    skill_names: list[str] | None = Field(default=None, max_length=32)


class ChatStateSnapshot(BaseModel):
    revision: int = Field(ge=0)
    sessions: list[ChatSessionMeta] = Field(max_length=30)
    session_data: dict[str, ChatSessionData]
    active_session_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "ChatStateSnapshot":
        session_ids = [session.id for session in self.sessions]
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("会话 ID 不可重复")
        unknown_data = set(self.session_data) - set(session_ids)
        if unknown_data:
            raise ValueError("会话数据包含未知会话")
        if self.active_session_id is not None and self.active_session_id not in session_ids:
            raise ValueError("当前会话不存在")
        payload = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
        if len(payload) > MAX_CHAT_STATE_CHARACTERS:
            raise ValueError("会话快照过大")
        return self


class ChatStateResponse(BaseModel):
    state: ChatStateSnapshot | None = None
    updated_at: float | None = None


class ChatToolPolicyInfo(BaseModel):
    """Purpose: 前端展示的工具运行策略。"""
    cost: Literal["low", "medium", "high"]
    cache_ttl_seconds: float = Field(ge=0)
    freshness: Literal["realtime", "near_realtime", "daily", "static"]
    scope: Literal["public", "user"]
    timeout_seconds: float | None = None
    max_parallel_calls: int | None = None
    max_result_characters: int


class ChatToolCapabilityInfo(BaseModel):
    """Purpose: 单个 Chat Tool 的公开能力定义。"""
    name: str
    description: str
    parameters: dict[str, Any]
    policy: ChatToolPolicyInfo
    skill_names: list[str] = Field(default_factory=list)


class ChatSkillCapabilityInfo(BaseModel):
    """Purpose: 单个 Chat Skill 的公开路由定义。"""
    name: str
    description: str
    triggers: list[str]
    tool_names: list[str]
    rules: list[str]
    exclusions: list[str]
    priority: int = Field(ge=0)


class ChatAgentCapabilityInfo(BaseModel):
    """Purpose: 单个专业 Agent 的公开能力定义。"""
    name: str
    display_name: str
    description: str
    tool_names: list[str]
    skill_names: list[str]
    max_rounds: int = Field(ge=1)


class ChatCapabilityAvailabilityInfo(BaseModel):
    status: Literal["ready", "degraded", "unavailable", "disabled"]
    reason: str


class ChatCapabilityAvailabilityResponse(BaseModel):
    llm: ChatCapabilityAvailabilityInfo
    skills: dict[str, ChatCapabilityAvailabilityInfo]
    agents: dict[str, ChatCapabilityAvailabilityInfo]


class ChatCapabilitiesResponse(BaseModel):
    """Purpose: 前端能力中心使用的 Skill、Agent 与 Tool 清单。"""
    skills: list[ChatSkillCapabilityInfo]
    agents: list[ChatAgentCapabilityInfo]
    tools: list[ChatToolCapabilityInfo]
    unassigned_tools: list[str] = Field(default_factory=list)
