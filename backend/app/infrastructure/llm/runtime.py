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
from app.infrastructure.llm.capabilities import LLMCapabilities
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
    ) -> None:
        self._model = model
        self.capabilities = capabilities
        self._api_key = api_key
        self._base_url = base_url
        self._api_version = api_version
        self._timeout = timeout
        self._max_retries = max_retries

    async def create(self, **kwargs):
        from litellm import acompletion

        kwargs = prepare_completion_kwargs(kwargs, self.capabilities, expected_model=self._model)
        kwargs.update(
            api_key=self._api_key,
            timeout=self._timeout,
            drop_params=True,
        )
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
            )
        )

    async def close(self) -> None:
        return None


class OpenAIAsyncCompletions:
    def __init__(self, completions: Any, capabilities: LLMCapabilities | None = None, model: str | None = None) -> None:
        self._model = model
        self._completions = completions
        self.capabilities = capabilities

    async def create(self, **kwargs):
        return await self._completions.create(**prepare_completion_kwargs(kwargs, self.capabilities, expected_model=self._model))


class OpenAIAsyncClient:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        capabilities: LLMCapabilities | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client
        self.capabilities = capabilities
        self.chat = SimpleNamespace(
            completions=OpenAIAsyncCompletions(client.chat.completions, capabilities, model)
        )

    async def close(self) -> None:
        await self._client.close()


class OpenAISyncClient:
    def __init__(self, client: Any, capabilities: LLMCapabilities, model: str) -> None:
        self._model = model
        self._client = client
        self.capabilities = capabilities
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
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
        client=OpenAISyncClient(client, spec.effective_capabilities, spec.model), model=spec.model,
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
        client=openai_client_type(raw_client, capabilities=capabilities, model=spec.model),
        model=spec.model,
        capabilities=capabilities,
    )


def create_openai_chat_runtime(settings: Settings | None = None) -> OpenAIChatRuntime:
    settings = settings or get_effective_settings()
    return _create_openai_chat_runtime(
        resolve_llm_client_spec(settings),
        openai_factory=OpenAI,
        http_client_factory=httpx.Client,
    )


def create_async_openai_chat_runtime(
    settings: Settings | None = None, *, max_retries: int | None = 0,
) -> AsyncOpenAIChatRuntime:
    settings = settings or get_effective_settings()
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
