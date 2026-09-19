import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMRetryableError(RuntimeError):
    """A transient provider failure that can be retried safely."""


class LLMUpstreamResponseError(LLMRetryableError):
    """The provider returned an empty or non-JSON HTTP response."""


class LLMInvalidResponseError(RuntimeError):
    """The provider returned a non-retryable, incompatible completion response."""


class LLMEmptyResponseError(LLMRetryableError):
    """The provider returned a syntactically valid completion with no text."""


_TRANSIENT_LLM_ERROR_MARKERS = (
    "upstream returned failure",
    "upstream error",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
)


def normalize_retryable_llm_error(error: Exception) -> Exception:
    """Normalize transport-compatible failures that may arrive inside a HTTP 200 stream."""
    if isinstance(error, LLMRetryableError):
        return error
    status_code = getattr(error, "status_code", None)
    if status_code is None:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
    message = str(error).strip().lower()
    if status_code in {408, 409, 429} or (isinstance(status_code, int) and status_code >= 500):
        return LLMUpstreamResponseError("LLM 上游暂时不可用")
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


def is_reasoning_model(model: str) -> bool:
    model_name = model.rsplit("/", 1)[-1].lower()
    return model_name.startswith(("o1", "o3", "o4", "gpt-5"))


def prepare_completion_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Adjust Chat Completions arguments for reasoning model constraints."""
    prepared = dict(kwargs)
    if is_reasoning_model(str(prepared.get("model", ""))):
        prepared.pop("temperature", None)
        if "max_tokens" in prepared and "max_completion_tokens" not in prepared:
            prepared["max_completion_tokens"] = prepared.pop("max_tokens")
    return prepared


def extract_message_text(content: Any) -> str:
    """Normalize text and provider-specific content block responses."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


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
    ):
        self._http_client = http_client_factory(trust_env=False)
        self.client = openai_factory(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            http_client=self._http_client,
        )
        self.model = model
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
                **prepare_completion_kwargs(kwargs)
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
    ):
        self.api_key = api_key
        self.model = model
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
        kwargs: dict = prepare_completion_kwargs(
            {
                "model": self.model,
                "messages": messages,
                "api_key": self.api_key,
                "temperature": temperature,
                "timeout": self.timeout,
                "drop_params": True,
            }
        )
        if json_format:
            kwargs["response_format"] = {"type": "json_object"}
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.api_version:
            kwargs["api_version"] = self.api_version

        try:
            response = completion(**kwargs)
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
