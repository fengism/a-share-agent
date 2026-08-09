"""Agentic LLM 请求并发控制与观测。"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from app.configuration import get_settings
from app.core.metrics import metrics


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


_llm_limiter = _AdaptiveConcurrencyLimiter()


async def create_chat_completion(client, **kwargs) -> Any:
    """在全局排队槽位中执行一次非流式 Chat Completion。"""
    kwargs.setdefault("max_tokens", max(256, int(get_settings().chat_max_completion_tokens)))
    started_at = time.perf_counter()
    async with _llm_limiter.slot():
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            metrics.record_provider_attempt(
                "llm_chat",
                operation="completion",
                success=False,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error_type=type(exc).__name__,
            )
            raise
    metrics.record_provider_attempt(
        "llm_chat",
        operation="completion",
        success=True,
        duration_ms=(time.perf_counter() - started_at) * 1000,
    )
    return response


async def stream_chat_completion(client, **kwargs) -> AsyncGenerator[Any, None]:
    """在完整流式响应生命周期内持有全局 LLM 槽位。"""
    kwargs.setdefault("max_tokens", max(256, int(get_settings().chat_max_completion_tokens)))
    started_at = time.perf_counter()
    async with _llm_limiter.slot():
        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                yield chunk
        except Exception as exc:
            metrics.record_provider_attempt(
                "llm_chat",
                operation="stream",
                success=False,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error_type=type(exc).__name__,
            )
            raise
    metrics.record_provider_attempt(
        "llm_chat",
        operation="stream",
        success=True,
        duration_ms=(time.perf_counter() - started_at) * 1000,
    )
