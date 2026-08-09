import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import httpx
from openai import OpenAI

logger = logging.getLogger(__name__)


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
    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> str:
        """Run a synchronous chat completion and return response text."""
        ...


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

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> str:
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
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else "?"
            completion_tokens = usage.completion_tokens if usage else "?"
            logger.info(
                "LLM响应: model=%s, tokens=%s/%s",
                self.model,
                prompt_tokens,
                completion_tokens,
            )
            return content
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

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> str:
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
            logger.info("LiteLLM响应: model=%s, 响应长度=%s", self.model, len(content))
            return content
        except Exception as error:
            logger.error("LiteLLM调用失败: model=%s, error=%s", self.model, error, exc_info=True)
            raise
