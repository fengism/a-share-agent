from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

import httpx
from openai import AsyncOpenAI, OpenAI

from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings
from app.domain.llm import (
    describe_llm_account_error as describe_llm_account_error,
)
from app.domain.llm import (
    is_llm_connection_error as is_llm_connection_error,
)
from app.infrastructure.llm.adapters import merge_extra_body, prepare_completion_kwargs
from app.infrastructure.llm.capabilities import LLMCapabilities
from app.infrastructure.llm.pool import AsyncResourcePool
from app.infrastructure.llm.spec import LLMClientSpec, apply_task_model, resolve_llm_client_spec

_POOL_MAXSIZE = 16


@dataclass(frozen=True)
class OpenAIChatRuntime:
    client: Any
    model: str


@dataclass(frozen=True)
class AsyncOpenAIChatRuntime:
    client: Any
    model: str
    capabilities: LLMCapabilities = LLMCapabilities()


class LiteLLMAsyncCompletions:
    def __init__(
        self, *, api_key: str, base_url: str, api_version: str, timeout: float,
        max_retries: int | None = 0,
        capabilities: LLMCapabilities | None = None,
        model: str | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self.capabilities = capabilities
        self._extra_body = dict(extra_body or {})
        self._api_key = api_key
        self._base_url = base_url
        self._api_version = api_version
        self._timeout = timeout
        self._max_retries = max_retries

    async def create(self, **kwargs):
        from litellm import acompletion

        extra_body = merge_extra_body(self._extra_body, kwargs.pop("extra_body", None))
        if extra_body is not None:
            kwargs["extra_body"] = extra_body
        kwargs = prepare_completion_kwargs(kwargs, self.capabilities, expected_model=self._model)
        kwargs.update(
            api_key=self._api_key,
            drop_params=True,
        )
        # 构造时固定的超时是默认值；调用方显式给出的（长回答按预算抬过的）必须优先，
        # 否则 LiteLLM 路径会静默把单次读写上限按回默认，模型调用又被提前掐断。
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        if self._max_retries is not None:
            kwargs["num_retries"] = self._max_retries
        if self._base_url:
            kwargs["api_base"] = self._base_url
        if self._api_version:
            kwargs["api_version"] = self._api_version
        return await acompletion(**kwargs)


class LiteLLMAsyncClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        api_version: str = "",
        timeout: float,
        capabilities: LLMCapabilities | None = None,
        model: str | None = None,
        max_retries: int | None = 0,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.chat = SimpleNamespace(
            completions=LiteLLMAsyncCompletions(
                api_key=api_key,
                base_url=base_url,
                api_version=api_version,
                timeout=timeout,
                max_retries=max_retries,
                capabilities=capabilities,
                model=model,
                extra_body=extra_body,
            )
        )

    async def close(self) -> None:
        return None


class OpenAIAsyncCompletions:
    def __init__(
        self,
        completions: Any,
        capabilities: LLMCapabilities | None = None,
        model: str | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._completions = completions
        self.capabilities = capabilities
        self._extra_body = dict(extra_body or {})

    async def create(self, **kwargs):
        extra_body = merge_extra_body(self._extra_body, kwargs.pop("extra_body", None))
        if extra_body is not None:
            kwargs["extra_body"] = extra_body
        return await self._completions.create(**prepare_completion_kwargs(kwargs, self.capabilities, expected_model=self._model))


class OpenAIAsyncClient:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        capabilities: LLMCapabilities | None = None,
        model: str | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self.capabilities = capabilities
        self.chat = SimpleNamespace(
            completions=OpenAIAsyncCompletions(
                client.chat.completions, capabilities, model, extra_body=extra_body
            )
        )

    async def close(self) -> None:
        await self._client.close()


class OpenAISyncClient:
    def __init__(
        self,
        client: Any,
        capabilities: LLMCapabilities,
        model: str,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._client = client
        self.capabilities = capabilities
        self._extra_body = dict(extra_body or {})
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        extra_body = merge_extra_body(self._extra_body, kwargs.pop("extra_body", None))
        if extra_body is not None:
            kwargs["extra_body"] = extra_body
        return self._client.chat.completions.create(**prepare_completion_kwargs(kwargs, self.capabilities, expected_model=self._model))

    def close(self) -> None:
        self._client.close()


def _create_openai_chat_runtime(
    spec: LLMClientSpec,
    *,
    openai_factory: Callable[..., Any] = OpenAI,
    http_client_factory: Callable[..., Any] = httpx.Client,
) -> OpenAIChatRuntime:
    client = openai_factory(
        api_key=spec.api_key,
        base_url=spec.base_url,
        timeout=spec.timeout,
        max_retries=0,
        http_client=http_client_factory(trust_env=False),
    )
    return OpenAIChatRuntime(
        client=OpenAISyncClient(
            client, spec.effective_capabilities, spec.model, extra_body=spec.extra_body,
        ),
        model=spec.model,
    )


def _create_async_openai_chat_runtime(
    spec: LLMClientSpec,
    *,
    async_openai_factory: Callable[..., Any] = AsyncOpenAI,
    http_client_factory: Callable[..., Any] = httpx.AsyncClient,
    litellm_client_type: type = LiteLLMAsyncClient,
    openai_client_type: type = OpenAIAsyncClient,
    max_retries: int | None = 0,
) -> AsyncOpenAIChatRuntime:
    capabilities = spec.effective_capabilities
    if spec.api_mode == "litellm":
        return AsyncOpenAIChatRuntime(
            client=litellm_client_type(
                api_key=spec.api_key,
                base_url=spec.base_url,
                api_version=spec.api_version,
                timeout=spec.timeout,
                capabilities=capabilities,
                model=spec.model,
                extra_body=spec.extra_body,
                **({"max_retries": max_retries} if max_retries is not None else {}),
            ),
            model=spec.model,
            capabilities=capabilities,
        )
    raw_client = async_openai_factory(
        api_key=spec.api_key,
        base_url=spec.base_url,
        timeout=spec.timeout,
        max_retries=0 if max_retries is None else max_retries,
        http_client=http_client_factory(trust_env=False),
    )
    return AsyncOpenAIChatRuntime(
        client=openai_client_type(
            raw_client, capabilities=capabilities, model=spec.model, extra_body=spec.extra_body,
        ),
        model=spec.model,
        capabilities=capabilities,
    )


def create_openai_chat_runtime(
    settings: Settings | None = None, *, simple: bool = False, task: str | None = None,
) -> OpenAIChatRuntime:
    settings = apply_task_model(settings or get_effective_settings(), simple=simple, task=task)
    return _create_openai_chat_runtime(
        resolve_llm_client_spec(settings),
        openai_factory=OpenAI,
        http_client_factory=httpx.Client,
    )


def create_async_openai_chat_runtime(
    settings: Settings | None = None, *, max_retries: int | None = 0, simple: bool = False, task: str | None = None,
) -> AsyncOpenAIChatRuntime:
    settings = apply_task_model(settings or get_effective_settings(), simple=simple, task=task)
    return _create_async_openai_chat_runtime(
        resolve_llm_client_spec(settings),
        async_openai_factory=AsyncOpenAI,
        http_client_factory=httpx.AsyncClient,
        litellm_client_type=LiteLLMAsyncClient,
        openai_client_type=OpenAIAsyncClient,
        max_retries=max_retries,
    )


async def _close_async_runtime(runtime: AsyncOpenAIChatRuntime) -> None:
    await runtime.client.close()


_async_runtime_pool: AsyncResourcePool[AsyncOpenAIChatRuntime] = AsyncResourcePool(
    maxsize=_POOL_MAXSIZE,
    close=_close_async_runtime,
)


@asynccontextmanager
async def borrow_async_openai_chat_runtime(
    settings: Settings | None = None, *, simple: bool = False, task: str | None = None,
) -> AsyncIterator[AsyncOpenAIChatRuntime]:
    settings = apply_task_model(settings or get_effective_settings(), simple=simple, task=task)
    client_spec = resolve_llm_client_spec(settings)
    async with _async_runtime_pool.borrow(
        client_spec.key,
        lambda: create_async_openai_chat_runtime(settings),
    ) as chat_runtime:
        yield chat_runtime


async def close_async_runtime_pool() -> None:
    await _async_runtime_pool.close_all()
