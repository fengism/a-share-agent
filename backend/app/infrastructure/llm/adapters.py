import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from openai import APIConnectionError, APITimeoutError, OpenAI

from app.domain.agent_llm import extract_message_text as extract_message_text
from app.domain.llm import (
    LLMConfigurationError,
)
from app.domain.llm import (
    LLMEmptyResponseError as LLMEmptyResponseError,
)
from app.domain.llm import (
    LLMInvalidResponseError as LLMInvalidResponseError,
)
from app.domain.llm import (
    LLMRetryableError as LLMRetryableError,
)
from app.domain.llm import (
    LLMUpstreamResponseError as LLMUpstreamResponseError,
)
from app.infrastructure.llm.capabilities import (
    LLMCapabilities,
    model_parameter_defaults,
)
from app.infrastructure.llm.capabilities import (
    is_reasoning_model as is_reasoning_model,
)

logger = logging.getLogger(__name__)

_TRANSIENT_LLM_ERROR_MARKERS = (
    "upstream returned failure",
    "upstream error",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
)


def normalize_retryable_llm_error(error: Exception) -> Exception:
    """Normalize transport-compatible failures that may arrive inside a HTTP 200 stream."""
    if isinstance(error, (TimeoutError, APITimeoutError, httpx.TimeoutException, LLMInvalidResponseError)):
        return error  # A slow/already-started request must not be automatically replayed.
    if isinstance(error, LLMRetryableError):
        return error
    if isinstance(error, (APIConnectionError, httpx.TransportError)):
        return LLMUpstreamResponseError("LLM 上游连接失败")
    status_code = getattr(error, "status_code", None)
    if status_code is None:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
    message = str(error).strip().lower()
    if status_code in {408, 409, 429} or (isinstance(status_code, int) and status_code >= 500):
        return LLMUpstreamResponseError("LLM 上游暂时不可用", status_code=status_code)
    if isinstance(status_code, int):
        return error  # Never classify a 400/401/403 by matching its response body.
    if any(marker in message for marker in _TRANSIENT_LLM_ERROR_MARKERS):
        return LLMUpstreamResponseError("LLM 上游暂时不可用")
    return error


@dataclass(frozen=True, slots=True)
class LLMUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    text: str
    usage: LLMUsage | None
    model: str
    finish_reason: str | None = None


def _usage_value(usage: Any, *names: str) -> int | None:
    if usage is None:
        return None
    for name in names:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if value is not None:
            return int(value)
    return None


def extract_usage(response: Any) -> LLMUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return None
    return LLMUsage(
        prompt_tokens=_usage_value(usage, "prompt_tokens", "input_tokens"),
        completion_tokens=_usage_value(usage, "completion_tokens", "output_tokens"),
    )


def validate_chat_completion_response(response: Any) -> Any:
    """Validate the minimum SDK response shape used by Chat Completions callers.

    Do not include the raw response in errors: compatible gateways may return an
    authentication page or other sensitive body while still using HTTP 200.
    """
    if isinstance(response, (str, bytes, bytearray, dict)) or response is None:
        raise LLMInvalidResponseError("LLM 上游响应对象类型异常")

    choices = getattr(response, "choices", None)
    if choices is None:
        raise LLMInvalidResponseError("LLM 上游响应 choices 为空")
    try:
        first_choice = choices[0]
    except IndexError:
        raise LLMInvalidResponseError("LLM 上游响应 choices 为空") from None
    except (KeyError, TypeError):
        raise LLMInvalidResponseError("LLM 上游响应 choices 格式异常") from None
    if getattr(first_choice, "message", None) is None:
        raise LLMInvalidResponseError("LLM 上游响应缺少 message")
    return response


# SDK extra_body is merged after normal parameters. Never let it rewrite fields
# already governed here; vendor-only extensions remain available unchanged.
_GOVERNED_BODY_FIELDS = frozenset({
    "model", "messages", "stream", "max_tokens", "max_completion_tokens",
    "temperature", "response_format", "stream_options", "tools", "tool_choice",
    "parallel_tool_calls",
})


def _validate_extra_body(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise LLMConfigurationError("extra_body 必须是 JSON 对象")
    if any(key in value for key in _GOVERNED_BODY_FIELDS):
        # Do not include values: extensions may contain secrets or prompt data.
        raise LLMConfigurationError("extra_body 不能覆盖受治理的模型、消息、预算或协议参数，请使用顶层参数")


def _validate_token_limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LLMConfigurationError("输出 token 预算必须是正整数")
    return value


def prepare_completion_kwargs(
    kwargs: dict[str, Any], capabilities: LLMCapabilities | None = None,
    *, expected_model: str | None = None,
) -> dict[str, Any]:
    """Idempotent request shaping shared by all SDK adapters and transports.

    A resolved route policy always wins over alias hints. Do not infer provider
    capabilities again after an explicit model/gateway override was selected.
    """
    prepared = dict(kwargs)
    _validate_extra_body(prepared.get("extra_body"))
    if expected_model is not None and prepared.get("model") != expected_model:
        raise LLMConfigurationError("请求模型与客户端兼容策略不一致，请为目标模型重新创建客户端")
    policy = capabilities or model_parameter_defaults(str(prepared.get("model", "")))
    if not policy.supports_temperature:
        prepared.pop("temperature", None)
    token_limits = [prepared.pop(key) for key in ("max_tokens", "max_completion_tokens") if prepared.get(key) is not None]
    prepared.pop("max_tokens", None)
    prepared.pop("max_completion_tokens", None)
    if policy.max_completion_tokens is not None:
        token_limits.append(policy.max_completion_tokens)
    if token_limits:
        prepared[policy.token_parameter] = min(_validate_token_limit(value) for value in token_limits)
    response_format = prepared.get("response_format")
    if isinstance(response_format, dict):
        if response_format.get("type") == "json_object" and not policy.json_mode:
            prepared.pop("response_format")  # Prompt/parser validation still applies.
        elif response_format.get("type") == "json_schema" and not policy.supports_strict_json_schema:
            raise LLMConfigurationError("当前模型网关未启用严格 JSON Schema，请配置兼容能力或使用 JSON 对象模式")
    if not prepared.get("stream") or not policy.stream_include_usage:
        prepared.pop("stream_options", None)
    if prepared.get("tool_choice") == "none" and not policy.supports_tool_choice_none:
        prepared.pop("tools", None)
    if prepared.get("tools"):
        if not policy.native_tool_calling:
            raise LLMConfigurationError("当前模型网关未启用工具调用能力")
        if prepared.get("stream") and not policy.streaming_tool_calls:
            raise LLMConfigurationError("当前模型网关未启用流式工具调用，请使用非流式工具轮次")
        if isinstance(prepared.get("tool_choice"), dict) and not policy.supports_named_tool_choice:
            raise LLMConfigurationError("当前模型网关未启用强制指定工具能力，请改用 auto 或配置兼容能力")
        if not policy.parallel_tool_calls:
            prepared.pop("parallel_tool_calls", None)
        if prepared.get("tool_choice") == "required" and not policy.supports_tool_choice_required:
            prepared["tool_choice"] = "auto"
    else:
        prepared.pop("tool_choice", None)
        prepared.pop("parallel_tool_calls", None)
    return prepared


class LLMClient(ABC):
    @abstractmethod
    def chat_result(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> LLMCompletion:
        """Run a synchronous chat completion and return invocation-local metadata."""
        ...

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> str:
        return self.chat_result(
            messages,
            temperature=temperature,
            json_format=json_format,
        ).text


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        *,
        openai_factory: Callable[..., Any] = OpenAI,
        http_client_factory: Callable[..., Any] = httpx.Client,
        capabilities: LLMCapabilities | None = None,
    ):
        self._http_client = http_client_factory(trust_env=False)
        self.client = openai_factory(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
            http_client=self._http_client,
        )
        self.model = model
        self.capabilities = capabilities
        logger.info("初始化OpenAI兼容客户端: model=%s, base_url=%s", model, base_url)

    def close(self) -> None:
        try:
            self._http_client.close()
        except Exception:
            logger.warning("关闭 OpenAI 兼容客户端连接池失败", exc_info=True)

    def chat_result(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> LLMCompletion:
        logger.info(
            "LLM请求: model=%s, messages数=%s, temperature=%s",
            self.model,
            len(messages),
            temperature,
        )
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if json_format:
                kwargs["response_format"] = {"type": "json_object"}
            response = self.client.chat.completions.create(
                **prepare_completion_kwargs(kwargs, self.capabilities)
            )
            content = extract_message_text(response.choices[0].message.content)
            if not content.strip():
                raise LLMEmptyResponseError("LLM 上游返回空内容")
            usage = extract_usage(response)
            prompt_tokens = usage.prompt_tokens if usage else "?"
            completion_tokens = usage.completion_tokens if usage else "?"
            logger.info(
                "LLM响应: model=%s, tokens=%s/%s",
                self.model,
                prompt_tokens,
                completion_tokens,
            )
            return LLMCompletion(
                text=content,
                usage=usage,
                model=self.model,
                finish_reason=getattr(response.choices[0], "finish_reason", None),
            )
        except LLMRetryableError:
            raise
        except json.JSONDecodeError as error:
            normalized = LLMUpstreamResponseError(
                f"LLM 上游返回空响应或非 JSON 响应（解析位置 {error.pos}）"
            )
            logger.debug(
                "LLM响应解析失败: model=%s, error_type=json_decode, position=%s",
                self.model,
                error.pos,
            )
            raise normalized from error
        except Exception as error:
            logger.error("LLM调用失败: model=%s, error=%s", self.model, error, exc_info=True)
            raise


class LiteLLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 120.0,
        api_version: str = "",
        capabilities: LLMCapabilities | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.capabilities = capabilities
        self.base_url = base_url
        self.timeout = timeout
        self.api_version = api_version
        logger.info("初始化LiteLLM客户端: model=%s, base_url=%s", model, base_url)

    def chat_result(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> LLMCompletion:
        from litellm import completion

        logger.info("LiteLLM请求: model=%s, messages数=%s", self.model, len(messages))
        kwargs: dict = dict(
            {
                "model": self.model,
                "messages": messages,
                "api_key": self.api_key,
                "temperature": temperature,
                "timeout": self.timeout,
                "drop_params": True,
                "num_retries": 0,
            }
        )
        if json_format:
            kwargs["response_format"] = {"type": "json_object"}
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.api_version:
            kwargs["api_version"] = self.api_version

        try:
            response = completion(**prepare_completion_kwargs(kwargs, self.capabilities))
            content = extract_message_text(response.choices[0].message.content)
            if not content.strip():
                raise LLMEmptyResponseError("LiteLLM 上游返回空内容")
            usage = extract_usage(response)
            logger.info("LiteLLM响应: model=%s, 响应长度=%s", self.model, len(content))
            return LLMCompletion(
                text=content,
                usage=usage,
                model=self.model,
                finish_reason=getattr(response.choices[0], "finish_reason", None),
            )
        except LLMRetryableError:
            raise
        except json.JSONDecodeError as error:
            normalized = LLMUpstreamResponseError(
                f"LiteLLM 上游返回空响应或非 JSON 响应（解析位置 {error.pos}）"
            )
            logger.debug(
                "LiteLLM响应解析失败: model=%s, error_type=json_decode, position=%s",
                self.model,
                error.pos,
            )
            raise normalized from error
        except Exception as error:
            logger.error("LiteLLM调用失败: model=%s, error=%s", self.model, error, exc_info=True)
            raise
