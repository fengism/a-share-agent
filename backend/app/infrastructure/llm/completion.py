"""Shared LLM transport: one limiter, bounded retries, deadlines and telemetry."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from openai import APITimeoutError

from app.configuration import get_settings
from app.configuration.schema import Settings
from app.core.metrics import metrics
from app.infrastructure.llm.adapters import (
    LLMRetryableError,
    extract_usage,
    normalize_retryable_llm_error,
    prepare_completion_kwargs,
    validate_chat_completion_response,
)
from app.infrastructure.llm.capabilities import LLMCapabilities, apply_deployment_limits, capabilities_for_settings
from app.infrastructure.llm.policy import (
    LLMGenerationTimeoutError,
    call_settings,
    generation_scope,
    request_timeout_error,
)


@asynccontextmanager
async def _request_deadline(deadline: float | None):
    scope = asyncio.timeout_at(deadline)
    try:
        async with scope:
            yield
    except TimeoutError as error:
        if not scope.expired():
            raise
        raise LLMGenerationTimeoutError("模型生成总时限已耗尽，请检查模型网关状态或缩小任务范围后重试") from error


@asynccontextmanager
async def _stream_read_guard(deadline: float | None, read_timeout: float):
    """同时受全局 deadline 与单块读超时（read_timeout）双重保护，防止流挂起死等。"""
    now = asyncio.get_running_loop().time()
    effective_deadline = min(deadline, now + read_timeout) if deadline is not None else now + read_timeout
    scope = asyncio.timeout_at(effective_deadline)
    try:
        async with scope:
            yield
    except TimeoutError as error:
        if deadline is not None and now >= deadline:
            raise LLMGenerationTimeoutError("模型生成总时限已耗尽，请检查模型网关状态或缩小任务范围后重试") from error
        raise httpx.ReadTimeout(f"模型流式响应读取超时（超过 {read_timeout:.1f} 秒无响应）") from error


class _AdaptiveConcurrencyLimiter:
    def __init__(self) -> None:
        self._active = 0
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def slot(self, *, deadline: float | None = None):
        async with _request_deadline(deadline), self._condition:
            await self._condition.wait_for(
                lambda: self._active < max(1, int(get_settings().max_concurrent_llm_requests))
            )
            self._active += 1
        try:
            yield
        finally:
            async with self._condition:
                self._active = max(0, self._active - 1)
                self._condition.notify_all()


logger = logging.getLogger(__name__)
_STREAM_RETRY_BASE_SECONDS = 0.25
_RATE_LIMIT_RETRY_BASE_SECONDS = 2.0


def _compute_retry_delay(normalized: Exception, attempt: int) -> float:
    """计算重试延迟：针对 429 限流使用更大的退避等待（2s, 4s...），其他临时错误沿用 0.25s。"""
    is_rate_limit = getattr(normalized, "status_code", None) == 429 or "429" in str(normalized)
    base = _RATE_LIMIT_RETRY_BASE_SECONDS if is_rate_limit else _STREAM_RETRY_BASE_SECONDS
    return float(base * (2 ** (attempt - 1)))


_llm_limiter = _AdaptiveConcurrencyLimiter()


def _prepare_request(
    client: Any, kwargs: dict[str, Any], *, settings: Settings, max_completion_tokens: int | None,
) -> dict[str, Any]:
    """Keep both explicit budgets until shared shaping computes their minimum."""
    request = dict(kwargs)
    capabilities = getattr(client, "capabilities", None)
    if not isinstance(capabilities, LLMCapabilities):
        capabilities = capabilities_for_settings(settings, model=str(request.get("model", settings.llm_model)))
    capabilities = apply_deployment_limits(capabilities, settings)
    if max_completion_tokens is not None:
        request["max_completion_tokens"] = max_completion_tokens
    if request.get("max_tokens") is None and request.get("max_completion_tokens") is None:
        request["max_tokens"] = settings.chat_max_completion_tokens
    if request.get("stream") and capabilities.stream_include_usage:
        request.setdefault("stream_options", {"include_usage": True})
    return prepare_completion_kwargs(request, capabilities)


async def create_chat_completion(
    client,
    *,
    metric_stage: str = "agentic.completion@v1",
    max_completion_tokens: int | None = None,
    request_timeout: float | None = None,
    **kwargs,
) -> Any:
    """在全局排队槽位中执行一次非流式 Chat Completion。"""
    settings = call_settings()
    request_kwargs = _prepare_request(client, kwargs, settings=settings, max_completion_tokens=max_completion_tokens)
    if request_timeout is not None:
        # 单次读写上限在客户端构造时就固定了（llm_timeout_seconds），不随执行上下文收缩。
        # 长回答必须显式把它抬到本次调用真正拿到的预算，否则最内层的传输限制会先于
        # generation_scope 触发，把「预算不够」误报成「读取响应超时」。
        request_kwargs["timeout"] = max(float(request_timeout), float(settings.llm_timeout_seconds))
    started_at = time.perf_counter()
    async with generation_scope(settings, timeout_seconds=settings.llm_generation_timeout_seconds), _llm_limiter.slot():
        queue_wait_ms = (time.perf_counter() - started_at) * 1000
        try:
            for attempt in range(1, settings.llm_max_attempts + 1):
                try:
                    response = await client.chat.completions.create(**request_kwargs)
                    validate_chat_completion_response(response)
                    break
                except Exception as error:
                    normalized = normalize_retryable_llm_error(error)
                    if not isinstance(normalized, LLMRetryableError) or attempt >= settings.llm_max_attempts:
                        if normalized is error:
                            raise
                        raise normalized from error
                    await asyncio.sleep(_compute_retry_delay(normalized, attempt))
        except asyncio.CancelledError:
            duration_ms = (time.perf_counter() - started_at) * 1000
            metrics.record_llm_prompt(
                metric_stage,
                str(request_kwargs.get("model", "")),
                success=False,
                duration_ms=duration_ms,
                queue_wait_ms=queue_wait_ms,
                cancelled=True,
                error_type="CancelledError",
            )
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000
            metrics.record_provider_attempt(
                "llm_chat",
                operation="completion",
                success=False,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
            )
            metrics.record_llm_prompt(
                metric_stage,
                str(request_kwargs.get("model", "")),
                success=False,
                duration_ms=duration_ms,
                queue_wait_ms=queue_wait_ms,
                error_type=type(exc).__name__,
            )
            raise
    duration_ms = (time.perf_counter() - started_at) * 1000
    usage = extract_usage(response)
    metrics.record_provider_attempt(
        "llm_chat",
        operation="completion",
        success=True,
        duration_ms=duration_ms,
    )
    metrics.record_llm_prompt(
        metric_stage,
        str(request_kwargs.get("model", "")),
        success=True,
        duration_ms=duration_ms,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        queue_wait_ms=queue_wait_ms,
    )
    return response


async def _close_provider_stream(stream: Any) -> None:
    """Close provider response bodies on success, failure, cancellation and generator close."""
    close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
    if not callable(close):
        return
    try:
        async with asyncio.timeout(5):
            result = close()
            if inspect.isawaitable(result):
                await result
    except Exception as exc:
        # 清理失败不能覆盖原始请求异常，也不能触发已完成请求的重试。
        logger.warning("LLM stream cleanup failed: error_type=%s", type(exc).__name__)


async def stream_chat_completion(
    client,
    *,
    metric_stage: str = "agentic.stream@v1",
    max_completion_tokens: int | None = None,
    request_timeout: float | None = None,
    **kwargs,
) -> AsyncGenerator[Any, None]:
    """Hold one LLM slot for the stream and retry transient failures before the first chunk."""
    settings = call_settings()
    request_kwargs = _prepare_request(client, kwargs, settings=settings, max_completion_tokens=max_completion_tokens)
    if request_timeout is not None:
        # Internal budget name must never reach provider SDKs. OpenAI/LiteLLM
        # both support the public per-request ``timeout`` option.
        request_kwargs["timeout"] = max(float(request_timeout), float(settings.llm_timeout_seconds))
    started_at = time.perf_counter()
    usage = None
    ttft_ms = None
    yielded_chunk = False
    deadline = asyncio.get_running_loop().time() + settings.llm_generation_timeout_seconds
    async with _llm_limiter.slot(deadline=deadline):
        queue_wait_ms = (time.perf_counter() - started_at) * 1000
        for attempt in range(1, settings.llm_max_attempts + 1):
            read_timeout = float(settings.llm_timeout_seconds)
            try:
                async with _stream_read_guard(deadline, read_timeout):
                    stream = await client.chat.completions.create(**request_kwargs)
                try:
                    iterator = aiter(stream)
                    while True:
                        try:
                            async with _stream_read_guard(deadline, read_timeout):
                                chunk = await anext(iterator)
                        except StopAsyncIteration:
                            break
                        yielded_chunk = True
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - started_at) * 1000
                        usage = extract_usage(chunk) or usage
                        yield chunk
                finally:
                    await _close_provider_stream(stream)
                break
            except asyncio.CancelledError:
                duration_ms = (time.perf_counter() - started_at) * 1000
                metrics.record_llm_prompt(
                    metric_stage,
                    str(request_kwargs.get("model", "")),
                    success=False,
                    duration_ms=duration_ms,
                    queue_wait_ms=queue_wait_ms,
                    ttft_ms=ttft_ms,
                    cancelled=True,
                    error_type="CancelledError",
                )
                raise
            except Exception as exc:
                normalized = (
                    request_timeout_error(
                        exc, settings=settings, elapsed_seconds=time.perf_counter() - started_at,
                    )
                    if isinstance(exc, (TimeoutError, APITimeoutError, httpx.TimeoutException))
                    and not isinstance(exc, LLMGenerationTimeoutError)
                    else normalize_retryable_llm_error(exc)
                )
                can_retry = (
                    isinstance(normalized, LLMRetryableError)
                    and not yielded_chunk
                    and attempt < settings.llm_max_attempts
                )
                if can_retry:
                    delay = _compute_retry_delay(normalized, attempt)
                    metrics.record_provider_attempt(
                        "llm_chat",
                        operation="stream",
                        success=False,
                        duration_ms=(time.perf_counter() - started_at) * 1000,
                        error_type=type(normalized).__name__,
                    )
                    logger.info(
                        "LLM流式上游临时失败，准备重试: model=%s attempt=%s/%s delay=%.2fs error_type=%s",
                        request_kwargs.get("model", ""),
                        attempt,
                        settings.llm_max_attempts,
                        delay,
                        type(normalized).__name__,
                    )
                    async with _request_deadline(deadline):
                        await asyncio.sleep(delay)
                    continue

                duration_ms = (time.perf_counter() - started_at) * 1000
                metrics.record_provider_attempt(
                    "llm_chat",
                    operation="stream",
                    success=False,
                    duration_ms=duration_ms,
                    error_type=type(normalized).__name__,
                )
                metrics.record_llm_prompt(
                    metric_stage,
                    str(request_kwargs.get("model", "")),
                    success=False,
                    duration_ms=duration_ms,
                    queue_wait_ms=queue_wait_ms,
                    ttft_ms=ttft_ms,
                    error_type=type(normalized).__name__,
                )
                if normalized is exc:
                    raise
                raise normalized from exc

    duration_ms = (time.perf_counter() - started_at) * 1000
    metrics.record_provider_attempt(
        "llm_chat",
        operation="stream",
        success=True,
        duration_ms=duration_ms,
    )
    metrics.record_llm_prompt(
        metric_stage,
        str(request_kwargs.get("model", "")),
        success=True,
        duration_ms=duration_ms,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        queue_wait_ms=queue_wait_ms,
        ttft_ms=ttft_ms,
    )
