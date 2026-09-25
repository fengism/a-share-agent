"""Collect long structured completions without blocking threads or hidden retries."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.configuration.schema import Settings
from app.infrastructure.llm.adapters import (
    LLMCompletion,
    LLMEmptyResponseError,
    LLMInvalidResponseError,
    LLMUpstreamResponseError,
    extract_usage,
)
from app.infrastructure.llm.completion import stream_chat_completion
from app.infrastructure.llm.policy import LLMGenerationTimeoutError as LLMGenerationTimeoutError
from app.infrastructure.llm.policy import completion_token_limit
from app.infrastructure.llm.runtime import create_async_openai_chat_runtime
from app.infrastructure.llm.tool_calling import ChatCompletionStreamNormalizer

logger = logging.getLogger(__name__)


class StreamingLLMClient:
    def __init__(
        self, client: Any, model: str, *, max_tokens: int, include_usage: bool = True, json_mode: bool = True
    ) -> None:
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.include_usage = include_usage
        self.json_mode = json_mode

    async def chat_result(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        json_format: bool = False,
    ) -> LLMCompletion:
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        if self.include_usage:
            kwargs["stream_options"] = {"include_usage": True}
        if json_format and self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        started = time.monotonic()
        logger.info("LLM流式生成请求: model=%s messages=%s", self.model, len(messages))
        stream = stream_chat_completion(self.client, metric_stage="generation.stream@v1", **kwargs)
        normalizer = ChatCompletionStreamNormalizer()
        usage = None
        received_text = False
        try:
            async for chunk in stream:
                error = chunk.get("error") if isinstance(chunk, dict) else getattr(chunk, "error", None)
                if error:
                    raise LLMUpstreamResponseError("LLM 上游流式响应失败")
                choices = chunk.get("choices") if isinstance(chunk, dict) else getattr(chunk, "choices", None)
                if not isinstance(choices, (list, tuple)):
                    raise LLMInvalidResponseError("LLM 流式响应 choices 格式异常")
                usage = extract_usage(chunk) or usage
                delta = normalizer.add(chunk)
                if delta.content and not received_text:
                    received_text = True
                    logger.info("LLM流式生成首段文本: model=%s elapsed=%.2fs", self.model, time.monotonic() - started)
        finally:
            close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
            if close is not None:
                try:
                    async with asyncio.timeout(5):
                        closed = close()
                        if inspect.isawaitable(closed):
                            await closed
                except Exception as error:
                    logger.warning("LLM流关闭失败: error_type=%s", type(error).__name__)

        turn = normalizer.finish()
        # Valid JSON alone is not proof of success: reject truncation and missing terminal chunks.
        if turn.finish_reason != "stop" or turn.tool_calls:
            raise LLMInvalidResponseError("LLM 输出未正常结束，未保存不完整内容")
        if not turn.content.strip():
            raise LLMEmptyResponseError("LLM 返回了空内容")
        logger.info("LLM流式生成完成: model=%s elapsed=%.2fs", self.model, time.monotonic() - started)
        return LLMCompletion(turn.content, usage, self.model, turn.finish_reason)


@asynccontextmanager
async def streaming_llm_client(settings: Settings, *, max_tokens: int) -> AsyncIterator[StreamingLLMClient]:
    # Dedicated connection ownership guarantees prompt cancellation during headers/streaming.
    runtime = create_async_openai_chat_runtime(settings, max_retries=0)
    try:
        yield StreamingLLMClient(
            runtime.client,
            runtime.model,
            max_tokens=completion_token_limit(max_tokens, settings),
            include_usage=settings.llm_stream_include_usage,
            json_mode=settings.llm_json_mode_enabled,
        )
    finally:
        try:
            async with asyncio.timeout(5):
                await runtime.client.close()
        except Exception as error:
            logger.warning("LLM客户端关闭失败: error_type=%s", type(error).__name__)
