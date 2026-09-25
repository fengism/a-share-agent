from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import aclosing
from typing import Literal
from uuid import uuid4

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.events import AgentEvent, AgentReasoningSource
from app.agentic.orchestration.opinions import build_synthesis_guidance
from app.agentic.runtime.completion import completion_warning
from app.agentic.runtime.llm import stream_chat_completion
from app.core.errors import build_internal_error, log_internal_error
from app.core.metrics import metrics
from app.infrastructure.llm.adapters import LLMRetryableError, extract_message_text
from app.infrastructure.llm.runtime import describe_llm_account_error
from app.infrastructure.llm.tool_calling import AsyncLLMClient

logger = logging.getLogger(__name__)
_PARTIAL_SOURCE_WARNING = "部分专业分析未完整完成，综合结论可能受限"
_SYNTHESIS_INPUT_WARNING = "综合分析上下文已按预算截断，结论可能不完整"
_SYNTHESIS_FALLBACK_WARNING = "综合分析未完整生成，已返回各维度原始结果"
_SYNTHESIS_STREAM_INTERRUPTED_WARNING = "综合分析流式响应中断，已保留已生成内容"
_MAX_SYNTHESIS_WARNINGS = 8


def _truncate_text(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    if limit <= 0:
        return "", True
    marker = "…"
    if limit <= len(marker):
        return marker[:limit], True
    return value[: limit - len(marker)] + marker, True


def build_synthesis_input(
    message: str,
    results: Mapping[str, AgentExecutionResult],
    *,
    max_characters: int,
    coverage_warnings: Sequence[str] = (),
) -> tuple[str, bool]:
    limit = max(256, int(max_characters))
    items = list(results.values())
    truncated = False
    prefix_parts: list[str] = []
    guidance = build_synthesis_guidance(results)
    if guidance:
        guidance, guidance_truncated = _truncate_text(guidance, limit // 3)
        prefix_parts.append(guidance)
        truncated = truncated or guidance_truncated
    if coverage_warnings:
        coverage, coverage_truncated = _truncate_text(
            "## 分析覆盖限制（必须明确说明，不能视作已完成或无风险）\n"
            + "\n".join(f"- {warning}" for warning in coverage_warnings),
            limit // 4,
        )
        prefix_parts.append(coverage)
        truncated = truncated or coverage_truncated
    question, question_truncated = _truncate_text(message, limit // 4)
    prefix_parts.append(f"用户问题: {question}")
    prefix = "\n\n".join(prefix_parts) + "\n\n"
    truncated = truncated or question_truncated
    if not items:
        content, content_truncated = _truncate_text(prefix, limit)
        return content, truncated or content_truncated

    headers = [f"## {result.display_name}\n" for result in items]
    separator_length = 2 * max(0, len(items) - 1)
    available = max(0, limit - len(prefix) - sum(map(len, headers)) - separator_length)
    base_allowance, extra = divmod(available, len(items))
    parts: list[str] = []
    for index, (header, result) in enumerate(zip(headers, items)):
        allowance = base_allowance + int(index < extra)
        analysis, analysis_truncated = _truncate_text(result.analysis, allowance)
        truncated = truncated or analysis_truncated
        parts.append(header + analysis)
    content = prefix + "\n\n".join(parts)
    bounded, bounded_truncated = _truncate_text(content, limit)
    return bounded, truncated or bounded_truncated


async def stream_synthesis(
    message: str,
    results: Mapping[str, AgentExecutionResult],
    llm_client: AsyncLLMClient,
    model: str,
    *,
    system_prompt: str,
    prompt_ref: str = "agentic.synthesis@v1",
    temperature: float = 0.1,
    max_completion_tokens: int | None = None,
    max_input_characters: int = 60_000,
    coverage_warnings: Sequence[str] = (),
) -> AsyncGenerator[AgentEvent, None]:
    synthesis_input, truncated = build_synthesis_input(
        message,
        results,
        max_characters=max_input_characters,
        coverage_warnings=coverage_warnings,
    )
    warnings = list(dict.fromkeys(
        warning.strip()
        for warning in [*coverage_warnings, *(warning for result in results.values() for warning in result.warnings)]
        if warning.strip()
    ))
    if any(result.status == "partial" for result in results.values()) and not warnings:
        warnings.append(_PARTIAL_SOURCE_WARNING)
    # 综合阶段的直接失败必须优先于来源警告，不能被数量上限挤掉。
    synthesis_warnings: list[str] = []
    if truncated:
        metrics.record_agentic_event("synthesis_input_truncated")
        synthesis_warnings.append(_SYNTHESIS_INPUT_WARNING)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": synthesis_input},
    ]
    emitted_content = False
    reasoning_source = AgentReasoningSource(
        block_id=uuid4().hex, source="综合分析", stage="synthesis",
    )
    finish_reason: str | None = None
    try:
        stream = stream_chat_completion(
            llm_client,
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
            metric_stage=prompt_ref,
            max_completion_tokens=max_completion_tokens,
        )
        async with aclosing(stream):
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                chunk_finish_reason = getattr(choice, "finish_reason", None)
                if chunk_finish_reason is not None:
                    finish_reason = chunk_finish_reason
                reasoning = extract_message_text(getattr(choice.delta, "reasoning_content", ""))
                if reasoning:
                    yield AgentEvent(type="reasoning", content=reasoning, reasoning_source=reasoning_source)
                if choice.delta.content:
                    emitted_content = emitted_content or bool(choice.delta.content.strip())
                    yield AgentEvent(type="text", content=choice.delta.content)
        if not emitted_content:
            metrics.record_agentic_event("synthesis_fallback")
            synthesis_warnings.append(_SYNTHESIS_FALLBACK_WARNING)
            yield AgentEvent(type="text", content="\n综合分析未返回有效内容。\n")
            for result in results.values():
                yield AgentEvent(
                    type="text",
                    content=f"\n### {result.display_name}\n{result.analysis}\n",
                )
        finish_warning = completion_warning(finish_reason or "stream_error")
        if finish_warning:
            if finish_reason == "length":
                metrics.record_agentic_event("synthesis_output_truncated")
            synthesis_warnings.insert(0, f"综合分析：{finish_warning}")
    except Exception as exc:
        if isinstance(exc, LLMRetryableError) and emitted_content:
            logger.warning(
                "Agentic synthesis 流式响应中断，保留部分内容: error_type=%s",
                type(exc).__name__,
            )
            metrics.record_agentic_event("synthesis_stream_interrupted")
            synthesis_warnings.append(_SYNTHESIS_STREAM_INTERRUPTED_WARNING)
        else:
            if isinstance(exc, LLMRetryableError):
                error_id, detail = build_internal_error("模型服务暂时不可用，请稍后重试")
                logger.warning(
                    "Agentic synthesis 临时失败 error_id=%s error_type=%s",
                    error_id,
                    type(exc).__name__,
                )
            else:
                error_id, detail = log_internal_error(
                    logger,
                    "Agentic synthesis",
                    exc,
                    "综合分析生成失败",
                )
                # 账号/配置类错误（Key 无效、余额不足等）透出真实原因，
                # 完整异常仍保留在日志供错误编号关联。
                user_reason = describe_llm_account_error(exc)
                if user_reason is not None:
                    detail = f"{user_reason}（错误编号：{error_id}）"
            metrics.record_agentic_event("synthesis_fallback")
            synthesis_warnings.append(_SYNTHESIS_FALLBACK_WARNING)
            yield AgentEvent(type="text", content=f"\n{detail}\n")
            for result in results.values():
                yield AgentEvent(
                    type="text",
                    content=f"\n### {result.display_name}\n{result.analysis}\n",
                )

    bounded_warnings = list(dict.fromkeys([*synthesis_warnings, *warnings]))[:_MAX_SYNTHESIS_WARNINGS]
    status: Literal["completed", "partial"] = (
        "partial" if bounded_warnings else "completed"
    )
    yield AgentEvent(type="done", status=status, warnings=bounded_warnings)
