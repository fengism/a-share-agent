"""同步 LLM 客户端池与聊天调用。"""

import asyncio
import logging
from typing import cast

import httpx
from openai import OpenAI

from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings
from app.infrastructure.llm import adapters, spec
from app.infrastructure.llm.capabilities import LLMCapabilities
from app.infrastructure.llm.pool import SyncResourcePool

logger = logging.getLogger(__name__)

_POOL_MAXSIZE = 16


class _OpenAICompatibleClient(adapters.OpenAICompatibleClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        capabilities: LLMCapabilities,
        extra_body: dict | None = None,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            capabilities=capabilities,
            extra_body=extra_body,
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
            capabilities=client_spec.effective_capabilities,
            extra_body=client_spec.extra_body,
        )
    return adapters.LiteLLMClient(
        api_key=client_spec.api_key,
        model=client_spec.model,
        base_url=client_spec.base_url,
        timeout=client_spec.timeout,
        api_version=client_spec.api_version,
        capabilities=client_spec.effective_capabilities,
        extra_body=client_spec.extra_body,
    )


class _PooledLLMClient(adapters.LLMClient):
    def __init__(self, client_spec: spec.LLMClientSpec):
        self._spec = client_spec
        self.model = client_spec.model
        self.capabilities = client_spec.effective_capabilities

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


def create_llm_client(
    settings: Settings | None = None, *, simple: bool = False, task: str | None = None,
) -> adapters.LLMClient:
    if settings is None:
        settings = get_effective_settings()
    return _PooledLLMClient(
        spec.resolve_llm_client_spec(spec.apply_task_model(settings, simple=simple, task=task))
    )


async def llm_chat(
    messages: list[dict],
    temperature: float = 0.1,
    json_format: bool = False,
    settings: Settings | None = None,
    client: adapters.LLMClient | None = None,
    simple: bool = False,
    task: str | None = None,
) -> str:
    return (
        await llm_chat_result(
            messages,
            temperature=temperature,
            json_format=json_format,
            settings=settings,
            client=client,
            simple=simple,
            task=task,
        )
    ).text


async def llm_chat_result(
    messages: list[dict],
    temperature: float = 0.1,
    json_format: bool = False,
    settings: Settings | None = None,
    client: adapters.LLMClient | None = None,
    simple: bool = False,
    task: str | None = None,
) -> adapters.LLMCompletion:
    """执行一次对话调用；切到子模型的简单任务在子模型失败时回退主模型重试一次。"""
    base = settings or get_effective_settings()
    effective = spec.apply_task_model(base, simple=simple, task=task)
    if client is not None or effective is base:
        # 显式注入 client 或未启用子模型：无回退可言，直接调用一次。
        return await _llm_chat_once(
            messages, temperature=temperature, json_format=json_format, settings=effective, client=client
        )
    try:
        return await _llm_chat_once(
            messages, temperature=temperature, json_format=json_format, settings=effective, client=None
        )
    except Exception:
        logger.warning(
            "子模型调用失败，回退主模型 sub_model=%s task=%s",
            effective.llm_model,
            task or ("simple" if simple else ""),
            exc_info=True,
        )
        return await _llm_chat_once(
            messages, temperature=temperature, json_format=json_format, settings=base, client=None
        )


async def _llm_chat_once(
    messages: list[dict],
    *,
    temperature: float,
    json_format: bool,
    settings: Settings,
    client: adapters.LLMClient | None,
) -> adapters.LLMCompletion:
    from app.infrastructure.llm.policy import generation_scope
    from app.infrastructure.llm.streaming import streaming_llm_client

    async with generation_scope(settings, timeout_seconds=settings.llm_generation_timeout_seconds):
        if client is not None:
            # Legacy injection only: Python cannot forcibly stop a caller-owned thread.
            return await asyncio.to_thread(
                client.chat_result, messages, temperature=temperature, json_format=json_format,
            )
        async with streaming_llm_client(settings, max_tokens=settings.llm_generation_max_completion_tokens) as managed:
            return await managed.chat_result(messages, temperature=temperature, json_format=json_format)


def close_llm_client_pool() -> None:
    _llm_client_pool.close_all()
