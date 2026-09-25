"""Validated deployment-only overrides; no credentials and no fuzzy URL matching."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_llm_endpoint(value: str) -> str:
    """Normalize only scheme/host, default ports and trailing path slash.

    Preserve path case and the complete query: proxies may route tenants there.
    This is a matching key, never a replacement request URL or credential scope.
    """
    try:
        # urlsplit silently drops tabs/newlines and leading controls. Reject them
        # before parsing so malformed input cannot acquire a trusted route policy.
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError
        value = value.strip(" ")
        if any(char.isspace() for char in value) or "\\" in value or "#" in value:
            raise ValueError
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError
        if parts.username is not None or parts.password is not None or parts.fragment:
            raise ValueError
        host = parts.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        port = parts.port
        if port is not None and (parts.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
            host += f":{port}"
        return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), parts.query, ""))
    except ValueError:
        raise ValueError("模型兼容配置需要不含用户凭据或片段的有效 HTTP(S) 网关地址") from None


class LLMCompatibilityOverride(BaseModel):
    """Exact target selectors; omitted model/mode/version means any on this gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    provider: str = Field(min_length=1)
    base_url: str = Field(min_length=1, repr=False)
    api_mode: Literal["openai", "litellm"] | None = None
    model: str | None = None
    api_version: str | None = None
    native_tool_calling: bool | None = None
    streaming_tool_calls: bool | None = None
    parallel_tool_calls: bool | None = None
    supports_tool_choice_none: bool | None = None
    supports_tool_choice_required: bool | None = None
    supports_named_tool_choice: bool | None = None
    replay_tool_reasoning: bool | None = None
    supports_strict_json_schema: bool | None = None
    json_mode: bool | None = None
    stream_include_usage: bool | None = None
    supports_temperature: bool | None = None
    token_parameter: Literal["max_tokens", "max_completion_tokens"] | None = None
    max_completion_tokens: int | None = Field(default=None, ge=1)

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("provider 不能为空")
        return value

    @field_validator("base_url")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        return normalize_llm_endpoint(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("model 必须是非空精确名称，不能含首尾空格；省略表示网关默认规则")
        return value
