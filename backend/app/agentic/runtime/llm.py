"""Agentic LLM 请求并发控制与观测。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from app.configuration import get_settings
from app.core.metrics import metrics
from app.infrastructure.llm.adapters import (
    LLMRetryableError,
    extract_usage,
    normalize_retryable_llm_error,
    prepare_completion_kwargs,
)


class _AdaptiveConcurrencyLimiter:
    def __init__(self) -> None:
        self._active = 0
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def slot(self):
        async with self._condition:
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
_STREAM_MAX_ATTEMPTS = 3
_STREAM_RETRY_BASE_SECONDS = 0.25

_llm_limiter = _AdaptiveConcurrencyLimiter()


async def create_chat_completion(
    client,
    *,
    metric_stage: str = "agentic.completion@v1",
    max_completion_tokens: int | None = None,
    **kwargs,
) -> Any:
    """在全局排队槽位中执行一次非流式 Chat Completion。"""
    token_limit = (
        get_settings().chat_max_completion_tokens
        if max_completion_tokens is None
        else max_completion_tokens
    )
    kwargs.setdefault("max_tokens", max(256, int(token_limit)))
    request_kwargs = prepare_completion_kwargs(kwargs)
    started_at = time.perf_counter()
    async with _llm_limiter.slot():
        queue_wait_ms = (time.perf_counter() - started_at) * 1000
        try:
            response = await client.chat.completions.create(**request_kwargs)
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


async def stream_chat_completion(
    client,
    *,
    metric_stage: str = "agentic.stream@v1",
    max_completion_tokens: int | None = None,
    **kwargs,
) -> AsyncGenerator[Any, None]:
    """Hold one LLM slot for the stream and retry transient failures before the first chunk."""
    token_limit = (
        get_settings().chat_max_completion_tokens
        if max_completion_tokens is None
        else max_completion_tokens
    )
    kwargs.setdefault("max_tokens", max(256, int(token_limit)))
    request_kwargs = prepare_completion_kwargs(kwargs)
    started_at = time.perf_counter()
    usage = None
    ttft_ms = None
    yielded_chunk = False
    async with _llm_limiter.slot():
        queue_wait_ms = (time.perf_counter() - started_at) * 1000
        for attempt in range(1, _STREAM_MAX_ATTEMPTS + 1):
            try:
                stream = await client.chat.completions.create(**request_kwargs)
                async for chunk in stream:
                    yielded_chunk = True
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - started_at) * 1000
                    usage = extract_usage(chunk) or usage
                    yield chunk
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
                normalized = normalize_retryable_llm_error(exc)
                can_retry = (
                    isinstance(normalized, LLMRetryableError)
                    and not yielded_chunk
                    and attempt < _STREAM_MAX_ATTEMPTS
                )
                if can_retry:
                    delay = _STREAM_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
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
                        _STREAM_MAX_ATTEMPTS,
                        delay,
                        type(normalized).__name__,
                    )
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
