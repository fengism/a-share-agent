import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.configuration import Settings, get_effective_settings
from app.core.metrics import metrics
from app.domain.prompting import PromptTrace
from app.infrastructure.llm.adapters import LLMClient
from app.infrastructure.llm.policy import generation_scope
from app.infrastructure.llm.prompting.spec import PromptContext, PromptSpec
from app.infrastructure.llm.streaming import StreamingLLMClient, streaming_llm_client
from app.infrastructure.llm.sync_client import llm_chat_result

logger = logging.getLogger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class PromptRun(Generic[OutputT]):
    value: OutputT
    trace: PromptTrace


class PromptExecutionError(ValueError):
    def __init__(self, message: str, *, raw_response: str, trace: PromptTrace):
        super().__init__(message)
        self.raw_response = raw_response
        self.trace = trace


def _input_digest(messages: list[dict[str, str]]) -> str:
    serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _trace(
    spec: PromptSpec, messages: list[dict[str, str]], model: str, temperature: float,
) -> PromptTrace:
    return PromptTrace(
        prompt_id=spec.id,
        prompt_version=spec.version,
        model=model,
        temperature=temperature,
        input_digest=_input_digest(messages),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


async def run_structured_prompt(
    spec: PromptSpec[OutputT], context: PromptContext, *, settings: Settings | None = None,
    client: LLMClient | None = None, temperature: float | None = None,
    async_client: StreamingLLMClient | None = None,
    timeout_seconds: float | None = None, max_tokens: int | None = None,
) -> PromptRun[OutputT]:
    if client is not None and async_client is not None:
        raise ValueError("Specify only one LLM client")
    settings = settings or get_effective_settings()
    timeout = settings.llm_generation_timeout_seconds if timeout_seconds is None else timeout_seconds
    async with generation_scope(settings, timeout_seconds=timeout):
        if client is not None or async_client is not None:
            return await _run_structured_prompt(
                spec, context, settings=settings, client=client,
                temperature=temperature, async_client=async_client,
            )
        async with streaming_llm_client(
            settings, max_tokens=max_tokens if max_tokens is not None else settings.llm_generation_max_completion_tokens,
        ) as managed_client:
            return await _run_structured_prompt(
                spec, context, settings=settings, async_client=managed_client, temperature=temperature,
            )


async def _run_structured_prompt(
    spec: PromptSpec[OutputT],
    context: PromptContext,
    *,
    settings: Settings | None = None,
    client: LLMClient | None = None,
    temperature: float | None = None,
    async_client: StreamingLLMClient | None = None,
) -> PromptRun[OutputT]:
    """渲染、执行并校验一个结构化 Prompt，失败时按规格执行修复重试。"""
    if client is not None and async_client is not None:
        raise ValueError("Specify only one LLM client")
    effective_temperature = spec.temperature if temperature is None else temperature
    messages = spec.render(context)
    trace = _trace(spec, messages, str(getattr(async_client or client, "model", "")), effective_temperature)
    raw_response = ""
    parse_error: Exception | None = None
    prompt_tokens = 0
    completion_tokens = 0

    for attempt in range(spec.repair_attempts + 1):
        request_messages = messages
        request_temperature = effective_temperature
        if attempt > 0:
            request_temperature = 0.0
            request_messages = messages + [
                {"role": "assistant", "content": raw_response},
                {
                    "role": "user",
                    "content": (
                        "上一版输出未通过 JSON Schema/Pydantic 校验。"
                        f"错误：{str(parse_error)[:1000]}\n请只重新输出修复后的完整 JSON 对象。"
                    ),
                },
            ]
        started_at = time.perf_counter()
        try:
            if async_client is not None:
                completion = await async_client.chat_result(
                    request_messages, temperature=request_temperature, json_format=True,
                )
            else:
                completion = await llm_chat_result(
                    request_messages,
                    temperature=request_temperature,
                    json_format=True,
                    settings=settings,
                    client=client,
                )
            raw_response = completion.text
        except Exception as error:
            metrics.record_llm_prompt(
                spec.ref,
                trace.model,
                success=False,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error_type=type(error).__name__,
            )
            raise
        duration_ms = (time.perf_counter() - started_at) * 1000
        usage = completion.usage
        attempt_prompt_tokens = getattr(usage, "prompt_tokens", None)
        attempt_completion_tokens = getattr(usage, "completion_tokens", None)
        prompt_tokens += attempt_prompt_tokens or 0
        completion_tokens += attempt_completion_tokens or 0
        try:
            value = spec.parse(raw_response)
            metrics.record_llm_prompt(
                spec.ref,
                trace.model,
                success=True,
                duration_ms=duration_ms,
                prompt_tokens=attempt_prompt_tokens,
                completion_tokens=attempt_completion_tokens,
            )
            completed_trace = trace.model_copy(
                update={
                    "attempts": attempt + 1,
                    "prompt_tokens": prompt_tokens or None,
                    "completion_tokens": completion_tokens or None,
                }
            )
            logger.info(
                "Prompt 执行成功: prompt=%s model=%s attempts=%s digest=%s",
                spec.ref,
                completed_trace.model,
                completed_trace.attempts,
                completed_trace.input_digest[:12],
            )
            return PromptRun(value=value, trace=completed_trace)
        except (TypeError, ValueError) as exc:
            parse_error = exc
            metrics.record_llm_prompt(
                spec.ref,
                trace.model,
                success=False,
                duration_ms=duration_ms,
                prompt_tokens=attempt_prompt_tokens,
                completion_tokens=attempt_completion_tokens,
                error_type=type(exc).__name__,
            )
            logger.warning("Prompt 输出校验失败: prompt=%s attempt=%s error=%s", spec.ref, attempt + 1, exc)

    failed_trace = trace.model_copy(
        update={
            "attempts": spec.repair_attempts + 1,
            "prompt_tokens": prompt_tokens or None,
            "completion_tokens": completion_tokens or None,
        }
    )
    raise PromptExecutionError(
        f"Prompt 输出在 {failed_trace.attempts} 次尝试后仍未通过校验: {parse_error}",
        raw_response=raw_response,
        trace=failed_trace,
    )
