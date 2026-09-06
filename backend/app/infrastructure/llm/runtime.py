from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

import httpx
from openai import AsyncOpenAI, OpenAI

from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings
from app.infrastructure.llm.adapters import prepare_completion_kwargs
from app.infrastructure.llm.pool import AsyncResourcePool
from app.infrastructure.llm.spec import LLMClientSpec, resolve_llm_client_spec

_POOL_MAXSIZE = 16


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


@dataclass(frozen=True)
class OpenAIChatRuntime:
    client: Any
    model: str


@dataclass(frozen=True)
class AsyncOpenAIChatRuntime:
    client: Any
    model: str


class LiteLLMAsyncCompletions:
    def __init__(self, *, api_key: str, base_url: str, api_version: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._api_version = api_version
        self._timeout = timeout

    async def create(self, **kwargs):
        from litellm import acompletion

        kwargs = prepare_completion_kwargs(kwargs)
        kwargs.update(
            api_key=self._api_key,
            timeout=self._timeout,
            drop_params=True,
        )
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
    ) -> None:
        self.chat = SimpleNamespace(
            completions=LiteLLMAsyncCompletions(
                api_key=api_key,
                base_url=base_url,
                api_version=api_version,
                timeout=timeout,
            )
        )

    async def close(self) -> None:
        return None


class OpenAIAsyncCompletions:
    def __init__(self, completions: Any) -> None:
        self._completions = completions

    async def create(self, **kwargs):
        return await self._completions.create(**prepare_completion_kwargs(kwargs))


class OpenAIAsyncClient:
    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client
        self.chat = SimpleNamespace(
            completions=OpenAIAsyncCompletions(client.chat.completions)
        )

    async def close(self) -> None:
        await self._client.close()


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
        http_client=http_client_factory(trust_env=False),
    )
    return OpenAIChatRuntime(client=client, model=spec.model)


def _create_async_openai_chat_runtime(
    spec: LLMClientSpec,
    *,
    async_openai_factory: Callable[..., Any] = AsyncOpenAI,
    http_client_factory: Callable[..., Any] = httpx.AsyncClient,
    litellm_client_type: type = LiteLLMAsyncClient,
    openai_client_type: type = OpenAIAsyncClient,
) -> AsyncOpenAIChatRuntime:
    if spec.api_mode == "litellm":
        return AsyncOpenAIChatRuntime(
            client=litellm_client_type(
                api_key=spec.api_key,
                base_url=spec.base_url,
                api_version=spec.api_version,
                timeout=spec.timeout,
            ),
            model=spec.model,
        )
    raw_client = async_openai_factory(
        api_key=spec.api_key,
        base_url=spec.base_url,
        timeout=spec.timeout,
        http_client=http_client_factory(trust_env=False),
    )
    return AsyncOpenAIChatRuntime(
        client=openai_client_type(raw_client),
        model=spec.model,
    )


def create_openai_chat_runtime(settings: Settings | None = None) -> OpenAIChatRuntime:
    settings = settings or get_effective_settings()
    return _create_openai_chat_runtime(
        resolve_llm_client_spec(settings),
        openai_factory=OpenAI,
        http_client_factory=httpx.Client,
    )


def create_async_openai_chat_runtime(settings: Settings | None = None) -> AsyncOpenAIChatRuntime:
    settings = settings or get_effective_settings()
    return _create_async_openai_chat_runtime(
        resolve_llm_client_spec(settings),
        async_openai_factory=AsyncOpenAI,
        http_client_factory=httpx.AsyncClient,
        litellm_client_type=LiteLLMAsyncClient,
        openai_client_type=OpenAIAsyncClient,
    )


async def _close_async_runtime(runtime: AsyncOpenAIChatRuntime) -> None:
    await runtime.client.close()


_async_runtime_pool: AsyncResourcePool[AsyncOpenAIChatRuntime] = AsyncResourcePool(
    maxsize=_POOL_MAXSIZE,
    close=_close_async_runtime,
)


@asynccontextmanager
async def borrow_async_openai_chat_runtime(
    settings: Settings | None = None,
) -> AsyncIterator[AsyncOpenAIChatRuntime]:
    settings = settings or get_effective_settings()
    client_spec = resolve_llm_client_spec(settings)
    async with _async_runtime_pool.borrow(
        client_spec.key,
        lambda: create_async_openai_chat_runtime(settings),
    ) as chat_runtime:
        yield chat_runtime


async def close_async_runtime_pool() -> None:
    await _async_runtime_pool.close_all()
