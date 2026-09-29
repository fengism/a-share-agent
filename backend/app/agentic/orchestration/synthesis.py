from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import aclosing
from typing import Literal
from uuid import uuid4

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.events import AgentEvent, AgentReasoningSource
from app.agentic.orchestration.opinions import build_synthesis_guidance
from app.agentic.runtime.answer import AnswerTextStream, clean_answer
from app.agentic.runtime.completion import completion_warning
from app.agentic.runtime.llm import stream_chat_completion
from app.agentic.tools.calls import has_tool_call_markup
from app.core.errors import log_internal_error
from app.core.metrics import metrics
from app.infrastructure.llm.adapters import LLMRetryableError
from app.infrastructure.llm.policy import LLMGenerationTimeoutError
from app.infrastructure.llm.runtime import describe_llm_account_error
from app.infrastructure.llm.tool_calling import AsyncLLMClient, ChatCompletionStreamNormalizer

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
    normalizer = ChatCompletionStreamNormalizer()
    output_filter = AnswerTextStream()
    published = ""
    reasoning_source = AgentReasoningSource(
        block_id=uuid4().hex, source="综合分析", stage="synthesis",
    )
    finish_reason: str | None = None
    failure_detail = ""
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
                delta = normalizer.add(chunk)
                if delta.finish_reason is not None:
                    finish_reason = delta.finish_reason
                reasoning = delta.reasoning_content
                if reasoning:
                    yield AgentEvent(type="reasoning", content=reasoning, reasoning_source=reasoning_source)
                content = delta.content
                if content:
                    text = output_filter.feed(content)
                    if text:
                        published += text
                        yield AgentEvent(type="text", content=text)
    except asyncio.CancelledError:
        # 已完成句子已交付，不把取消转成成功，也不重新执行综合模型。
        raise
    except (LLMRetryableError, LLMGenerationTimeoutError, TimeoutError):
        synthesis_warnings.append(_SYNTHESIS_STREAM_INTERRUPTED_WARNING)
        metrics.record_agentic_event("synthesis_stream_interrupted")
    except Exception as exc:
        error_id, failure_detail = log_internal_error(logger, "Agentic synthesis", exc, "综合分析生成失败")
        user_reason = describe_llm_account_error(exc)
        if user_reason is not None:
            failure_detail = f"{user_reason}（错误编号：{error_id}）"
        synthesis_warnings.append(_SYNTHESIS_STREAM_INTERRUPTED_WARNING)

    tail = output_filter.flush()
    if tail:
        published += tail
        yield AgentEvent(type="text", content=tail)
    if has_tool_call_markup(normalizer.finish().content) or normalizer.finish().tool_calls:
        synthesis_warnings.append("综合分析输出了未执行的工具调用标记，已移除；结论仅基于已有证据")
    finish_warning = completion_warning(finish_reason or "stream_error")
    if finish_warning:
        if finish_reason == "length":
            metrics.record_agentic_event("synthesis_output_truncated")
        synthesis_warnings.insert(0, f"综合分析：{finish_warning}")
    if not clean_answer(published):
        metrics.record_agentic_event("synthesis_fallback")
        synthesis_warnings.append(_SYNTHESIS_FALLBACK_WARNING)
        if failure_detail:
            yield AgentEvent(type="text", content=f"\n{failure_detail}\n")
        for result in results.values():
            text = clean_answer(result.analysis) if result.status != "failed" else ""
            if text:
                published += text
                yield AgentEvent(type="text", content=f"\n### {result.display_name}\n{text}\n")
        if not clean_answer(published):
            yield AgentEvent(type="error", error="综合分析未生成有效结论，且没有可保留的有效分析")
            yield AgentEvent(type="done", status="failed", warnings=list(dict.fromkeys(synthesis_warnings + warnings)))
            return

    bounded_warnings = list(dict.fromkeys([*synthesis_warnings, *warnings]))[:_MAX_SYNTHESIS_WARNINGS]
    status: Literal["completed", "partial"] = (
        "partial" if bounded_warnings else "completed"
    )
    yield AgentEvent(type="done", status=status, warnings=bounded_warnings)
