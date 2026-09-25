"""Task deadlines and request policy shared by all asynchronous LLM paths."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

import httpx
from openai import APITimeoutError

from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings

_current_settings: ContextVar[Settings | None] = ContextVar("llm_call_settings", default=None)


class LLMGenerationTimeoutError(TimeoutError):
    """LLM timeout (deadline or transport); do not blindly restart a workflow."""


class LLMRequestTimeoutError(LLMGenerationTimeoutError):
    """The transport timed out before the enclosing generation deadline expired."""


def request_timeout_error(
    error: BaseException, *, settings: Settings, elapsed_seconds: float,
) -> LLMRequestTimeoutError:
    # Only expose a fixed category, never an upstream message, URL or credentials.
    phase = "请求"
    current: BaseException | None = error
    for _ in range(8):
        if isinstance(current, httpx.ConnectTimeout):
            phase = "连接"
            break
        if isinstance(current, httpx.ReadTimeout):
            phase = "读取响应"
            break
        if isinstance(current, httpx.WriteTimeout):
            phase = "发送请求"
            break
        if isinstance(current, httpx.PoolTimeout):
            phase = "等待连接池"
            break
        current = current.__cause__ if current is not None else None
    return LLMRequestTimeoutError(
        f"模型{phase}超时（本次调用已耗时 {elapsed_seconds:.1f} 秒；"
        f"客户端超时配置 {settings.llm_timeout_seconds:g} 秒；"
        f"生成总预算 {settings.llm_generation_timeout_seconds:g} 秒，非本次实际耗时），"
        "请检查模型网关状态或请求超时配置后重试"
    )


def call_settings() -> Settings:
    return _current_settings.get() or get_effective_settings()


@asynccontextmanager
async def generation_scope(
    settings: Settings,
    *,
    timeout_seconds: float,
    label: str = "模型生成",
) -> AsyncIterator[None]:
    """One wall-clock budget includes queueing, retries and all JSON repairs."""
    scoped_settings = settings.model_copy(update={"llm_generation_timeout_seconds": timeout_seconds})
    token = _current_settings.set(scoped_settings)
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    deadline = asyncio.timeout(timeout_seconds)
    try:
        async with deadline:
            yield
    except LLMGenerationTimeoutError:
        raise
    except (TimeoutError, APITimeoutError, httpx.TimeoutException) as error:
        elapsed_seconds = loop.time() - started_at
        if not deadline.expired():
            raise request_timeout_error(
                error, settings=scoped_settings, elapsed_seconds=elapsed_seconds,
            ) from error
        raise LLMGenerationTimeoutError(
            f"{label}总时限已耗尽（已耗时 {elapsed_seconds:.1f} 秒；时限 {timeout_seconds:g} 秒），"
            "请检查模型网关状态或缩小任务范围后重试"
        ) from error
    finally:
        _current_settings.reset(token)


def completion_token_limit(requested: int, settings: Settings) -> int:
    """Optional endpoint/model cap; never guess capacities from a model alias."""
    cap = settings.llm_model_max_completion_tokens
    return max(1, min(requested, cap) if cap is not None else requested)


def is_llm_failure(error: BaseException) -> bool:
    """Walk wrappers without string matching or exposing provider response bodies."""
    from app.domain.llm import LLMConfigurationError
    from app.infrastructure.llm.adapters import LLMInvalidResponseError, LLMRetryableError
    from app.infrastructure.llm.prompting.runner import PromptExecutionError

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
                PromptExecutionError,
            ),
        ):
            return True
        if type(current).__module__.split(".", 1)[0] in {"openai", "litellm"}:
            return True
        current = current.__cause__ or current.__context__
    return False
