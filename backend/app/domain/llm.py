"""Shared LLM contracts: configuration, transport errors and capabilities.

These types live in the domain layer so both the infrastructure adapters and
the agent runtime can depend on one identity without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


class LLMConfigurationError(ValueError):
    """The selected provider cannot be used with the effective configuration."""


class LLMRetryableError(RuntimeError):
    """A transient provider failure that can be retried safely."""


class LLMUpstreamResponseError(LLMRetryableError):
    """The provider returned an empty or non-JSON HTTP response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMInvalidResponseError(RuntimeError):
    """The provider returned a non-retryable, incompatible completion response."""


class LLMEmptyResponseError(LLMRetryableError):
    """The provider returned a syntactically valid completion with no text."""


class LLMGenerationTimeoutError(TimeoutError):
    """LLM timeout (deadline or transport); do not blindly restart a workflow."""


class LLMRequestTimeoutError(LLMGenerationTimeoutError):
    """The transport timed out before the enclosing generation deadline expired."""


class LLMFailureMarker:
    """Marker for non-LLM errors that should still be treated as model failures."""


@dataclass(frozen=True, slots=True)
class LLMCapabilities:
    native_tool_calling: bool = True
    streaming_tool_calls: bool = True
    parallel_tool_calls: bool = True
    supports_tool_choice_none: bool = True
    supports_tool_choice_required: bool = True
    supports_named_tool_choice: bool = True
    replay_tool_reasoning: bool = False
    supports_strict_json_schema: bool = False
    json_mode: bool = True
    stream_include_usage: bool = True
    supports_temperature: bool = True
    token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    max_completion_tokens: int | None = None


DEFAULT_LLM_CAPABILITIES = LLMCapabilities()


def is_reasoning_model(model: str) -> bool:
    # Legacy alias hint only; arbitrary deployment names require an explicit rule.
    return model.rsplit("/", 1)[-1].lower().startswith(("o1", "o3", "o4", "gpt-5"))


def model_parameter_defaults(model: str) -> LLMCapabilities:
    if is_reasoning_model(model):
        return replace(
            DEFAULT_LLM_CAPABILITIES,
            supports_temperature=False,
            token_parameter="max_completion_tokens",
        )
    return DEFAULT_LLM_CAPABILITIES


_LLM_CONNECTION_ERROR_NAMES = frozenset({
    "APIConnectionError",
    "APITimeoutError",
    "APIConnectionTimeoutError",
})


def is_llm_connection_error(error: BaseException) -> bool:
    """LLM 网关连不上（网络/代理故障）——可重试的上游错误，而非业务失败。

    openai 与 litellm 的连接类异常类名一致（APIConnectionError/APITimeoutError），
    按异常类名匹配以避免硬依赖具体 SDK；同时沿 __cause__ 链穿透包装层。
    """
    current: BaseException | None = error
    depth = 0
    while current is not None and depth < 8:
        if type(current).__name__ in _LLM_CONNECTION_ERROR_NAMES:
            return True
        current = current.__cause__
        depth += 1
    return False


_LLM_ACCOUNT_ERROR_MESSAGES: dict[int, str] = {
    401: "模型 API Key 无效或已过期，请在设置中检查模型配置",
    402: "模型服务余额不足，请充值或更换模型配置",
    403: "模型 API Key 无权限访问该模型，请在设置中检查模型配置",
    404: "模型不存在或接口地址错误，请在设置中检查模型配置",
}

_CONTEXT_LENGTH_MARKERS = (
    "context_length",
    "maximum context",
    "context window",
    "input length exceeds",
    "prompt is too long",
)


def describe_llm_account_error(error: BaseException) -> str | None:
    """将用户可自行解决的模型配置类错误映射为可操作的提示文案。

    每个用户在设置页配置自己的模型账号，Key 无效、余额不足等错误由用户
    自行处理，重试无意义，应透出真实原因而非脱敏成错误编号。未命中映射
    （瞬时故障、服务端错误等）返回 None，由调用方走既有脱敏兜底。
    openai 与 litellm 的状态码异常均带 ``status_code`` 属性，沿 __cause__
    链穿透包装层。
    """
    current: BaseException | None = error
    depth = 0
    while current is not None and depth < 8:
        status_code = getattr(current, "status_code", None)
        if isinstance(status_code, int):
            message = _LLM_ACCOUNT_ERROR_MESSAGES.get(status_code)
            if message is not None:
                return message
            if status_code == 400:
                text = str(current).lower()
                if any(marker in text for marker in _CONTEXT_LENGTH_MARKERS):
                    return "对话内容超出模型上下文长度，请精简问题后重试"
        current = current.__cause__
        depth += 1
    return None


def is_llm_failure(error: BaseException) -> bool:
    """Walk wrappers without string matching or exposing provider response bodies."""
    current: BaseException | None = error
    for _ in range(8):
        if current is None:
            return False
        if isinstance(
            current,
            (
                LLMGenerationTimeoutError,
                LLMConfigurationError,
                LLMInvalidResponseError,
                LLMRetryableError,
                LLMFailureMarker,
            ),
        ):
            return True
        if type(current).__module__.split(".", 1)[0] in {"openai", "litellm"}:
            return True
        current = current.__cause__ or current.__context__
    return False


__all__ = [
    "DEFAULT_LLM_CAPABILITIES",
    "LLMCapabilities",
    "LLMConfigurationError",
    "LLMEmptyResponseError",
    "LLMGenerationTimeoutError",
    "LLMFailureMarker",
    "LLMInvalidResponseError",
    "LLMRequestTimeoutError",
    "LLMRetryableError",
    "LLMUpstreamResponseError",
    "describe_llm_account_error",
    "is_llm_connection_error",
    "is_llm_failure",
    "is_reasoning_model",
    "model_parameter_defaults",
]
