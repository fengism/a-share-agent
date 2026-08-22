"""同步 LLM 客户端池与聊天调用。"""

import asyncio
import logging
from typing import cast

import httpx
from openai import OpenAI

from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings
from app.infrastructure.llm import adapters, spec
from app.infrastructure.llm.pool import SyncResourcePool

logger = logging.getLogger(__name__)

_POOL_MAXSIZE = 16
_TRANSIENT_RESPONSE_MAX_ATTEMPTS = 3
_TRANSIENT_RESPONSE_RETRY_BASE_SECONDS = 0.25


class _OpenAICompatibleClient(adapters.OpenAICompatibleClient):
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            openai_factory=OpenAI,
            http_client_factory=httpx.Client,
        )


def _close_llm_client(client: adapters.LLMClient) -> None:
    close = getattr(client, "close", None)
    if close is not None:
        close()


_llm_client_pool: SyncResourcePool[adapters.LLMClient] = SyncResourcePool(
    maxsize=_POOL_MAXSIZE,
    close=_close_llm_client,
)


def _build_llm_client(client_spec: spec.LLMClientSpec) -> adapters.LLMClient:
    logger.info(
        "创建LLM客户端: provider=%s, api_mode=%s, model=%s",
        client_spec.provider,
        client_spec.api_mode,
        client_spec.model,
    )
    if client_spec.api_mode == "openai":
        return _OpenAICompatibleClient(
            api_key=client_spec.api_key,
            base_url=client_spec.base_url,
            model=client_spec.model,
            timeout=client_spec.timeout,
        )
    return adapters.LiteLLMClient(
        api_key=client_spec.api_key,
        model=client_spec.model,
        base_url=client_spec.base_url,
        timeout=client_spec.timeout,
        api_version=client_spec.api_version,
    )


class _PooledLLMClient(adapters.LLMClient):
    def __init__(self, client_spec: spec.LLMClientSpec):
        self._spec = client_spec
        self.model = client_spec.model

    def chat_result(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> adapters.LLMCompletion:
        with _llm_client_pool.borrow(
            self._spec.key,
            lambda: _build_llm_client(self._spec),
        ) as client:
            return cast(
                adapters.LLMCompletion,
                client.chat_result(
                    messages,
                    temperature=temperature,
                    json_format=json_format,
                ),
            )


def create_llm_client(settings: Settings | None = None) -> adapters.LLMClient:
    if settings is None:
        settings = get_effective_settings()
    return _PooledLLMClient(spec.resolve_llm_client_spec(settings))


async def llm_chat(
    messages: list[dict],
    temperature: float = 0.1,
    json_format: bool = False,
    settings: Settings | None = None,
    client: adapters.LLMClient | None = None,
) -> str:
    return (
        await llm_chat_result(
            messages,
            temperature=temperature,
            json_format=json_format,
            settings=settings,
            client=client,
        )
    ).text


async def llm_chat_result(
    messages: list[dict],
    temperature: float = 0.1,
    json_format: bool = False,
    settings: Settings | None = None,
    client: adapters.LLMClient | None = None,
) -> adapters.LLMCompletion:
    if client is None:
        client = create_llm_client(settings)
    for attempt in range(1, _TRANSIENT_RESPONSE_MAX_ATTEMPTS + 1):
        try:
            return await asyncio.to_thread(
                client.chat_result,
                messages,
                temperature=temperature,
                json_format=json_format,
            )
        except adapters.LLMRetryableError as error:
            if attempt >= _TRANSIENT_RESPONSE_MAX_ATTEMPTS:
                logger.warning(
                    "LLM临时响应错误重试耗尽: model=%s attempts=%s error=%s",
                    getattr(client, "model", "unknown"),
                    attempt,
                    error,
                )
                raise
            delay = _TRANSIENT_RESPONSE_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "LLM临时响应错误，准备重试: model=%s attempt=%s/%s delay=%.2fs error=%s",
                getattr(client, "model", "unknown"),
                attempt,
                _TRANSIENT_RESPONSE_MAX_ATTEMPTS,
                delay,
                error,
            )
            await asyncio.sleep(delay)
    raise RuntimeError("LLM retry loop exited unexpectedly")


def close_llm_client_pool() -> None:
    _llm_client_pool.close_all()
