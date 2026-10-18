from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Collection
from contextlib import aclosing
from dataclasses import dataclass, field, replace
from typing import Any, Literal
from uuid import uuid4

from app.agentic.agents.contracts import (
    AgentExecutionResult,
    AgentProfile,
    ToolExecutionSummary,
)
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent, AgentReasoningSource
from app.agentic.messages import build_messages
from app.agentic.orchestration.opinions import parse_opinion_block
from app.agentic.protocol import (
    AgentMessage,
    ToolCallInfo,
    ToolResultInfo,
)
from app.agentic.runtime.answer import AnswerTextStream, clean_answer
from app.agentic.runtime.completion import completion_warning
from app.agentic.runtime.context import AgentExecutionContext, ToolCallReservation
from app.agentic.runtime.evidence import (
    build_evidence_gap_report,
    safe_tool_failure_code,
    tool_failure_label,
)
from app.agentic.runtime.llm import create_chat_completion, stream_chat_completion
from app.agentic.runtime.metrics import metrics
from app.agentic.runtime.settings import get_default_settings
from app.agentic.runtime.tool_budget import budget_rejection_message
from app.agentic.semantics import EvidenceState, model_stop_code, result_status, stop_reason
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.calls import (
    build_assistant_tool_message,
    extract_pseudo_tool_calls,
    has_tool_call_markup,
    prepare_tool_call,
    strip_tool_call_markup,
)
from app.agentic.tools.serialization import (
    serialize_context_results,
    serialize_error,
)
from app.domain.agent_llm import (
    AsyncLLMClient,
    ChatCompletionStreamNormalizer,
    LLMCapabilities,
    LLMTurn,
    ToolChoice,
    capabilities_from_client,
    normalize_chat_completion,
    resolve_tool_request,
)
from app.domain.async_utils import wait_for_cleanup
from app.domain.errors import UpstreamUnavailableError, build_internal_error, log_internal_error
from app.domain.llm import (
    LLMGenerationTimeoutError,
    LLMInvalidResponseError,
    LLMRetryableError,
    describe_llm_account_error,
    is_llm_connection_error,
)

logger = logging.getLogger(__name__)
_EMPTY_OUTPUT_ERROR = "模型未生成有效回答，请稍后重试"
_TOOL_CONTEXT_WARNING = "工具上下文预算不足，部分证据已截断或未提供给模型，结论可能受限"
_TOOL_BUDGET_WARNING = "部分工具请求受额度限制未执行，具体原因见对应工具结果"
_TOOL_MARKUP_WARNING = "模型以正文形式输出了工具调用标记，已从回答中移除；结论仅基于已取得的证据"
_TOOL_OUTPUT_ERROR = "模型仍在请求工具而未生成有效结论，请检查模型工具调用兼容性后重试"
_REASONING_TRUNCATED_WARNING = "推理内容已按上下文预算截断，不影响工具证据与最终结论"
# Some thinking gateways require reasoning on tool turns, but it is not tool
# evidence. Cap each replayed turn and count it against the same context budget.
_MAX_REPLAY_REASONING_CHARACTERS = 8_000
_FINAL_ANSWER_INSTRUCTION = (
    "本次工具取证阶段已结束。现在只输出最终分析正文，不要再调用工具、输出工具调用标记，"
    "也不要停留在‘让我获取更多数据’等后续行动计划。仅依据对话中已取得的有效证据作答，"
    "明确区分已知事实、推断和未核实信息；缺少新闻或资金流向数据时明确说明，"
    "不得假装已查询、编造数据或据此给出确定性结论。"
)


def _bounded_replay_reasoning(
    reasoning_content: str,
    max_tool_context_characters: int,
) -> tuple[str, bool]:
    """Bound one replayed reasoning turn; returns ``(text, truncated)``."""
    cap = min(
        _MAX_REPLAY_REASONING_CHARACTERS,
        max(0, max_tool_context_characters // 4),
    )
    if len(reasoning_content) <= cap:
        return reasoning_content, False
    return reasoning_content[:cap], True


def _llm_request_timeout(
    execution_context: AgentExecutionContext | None, settings: Any
) -> float:
    """本次模型请求可用的单次读写上限：不能活过外层请求预算。

    工具调用早就用 ``bounded_timeout`` 跟着执行上下文的 deadline 收缩了，模型调用却一直
    按客户端构造时固定的 ``llm_timeout_seconds`` 掐断——最内层的传输限制先触发，失败原因
    被误报成「读取响应超时」，而实际上只是这次回答还没写完。生成总预算是天花板，外层请求
    预算（对话总时限）是地板：谁更紧听谁的。
    """
    budget = float(settings.llm_generation_timeout_seconds)
    if execution_context is None or execution_context.deadline is None:
        return budget
    return min(budget, max(float(execution_context.bounded_timeout(budget)), 1.0))


def _termination_error_reason(exc: Exception) -> str:
    if isinstance(exc, LLMInvalidResponseError):
        return "invalid_response"
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return {400: "bad_request", 401: "authentication_error", 403: "permission_error", 429: "rate_limited"}.get(code, "generation_error")
    return "generation_error"


def _log_agent_llm_error(operation: str, exc: Exception, public_message: str) -> tuple[str, str]:
    if isinstance(exc, LLMInvalidResponseError):
        error_id, detail = build_internal_error(
            "模型服务返回格式异常，请检查接口地址、API 模式与 OpenAI 兼容性"
        )
        logger.warning(
            "%s响应格式异常 error_id=%s error_type=%s",
            operation,
            error_id,
            type(exc).__name__,
        )
        return error_id, detail
    if isinstance(exc, LLMRetryableError):
        error_id, detail = build_internal_error("模型服务暂时不可用，请稍后重试")
        logger.warning(
            "%s临时失败 error_id=%s error_type=%s",
            operation,
            error_id,
            type(exc).__name__,
        )
        return error_id, detail
    error_id, detail = log_internal_error(logger, operation, exc, public_message)
    # 账号/配置类错误（Key 无效、余额不足等）由用户自行配置的模型账号引起，
    # 可自行解决，透出真实原因而非脱敏提示；完整异常仍保留在日志供关联。
    user_reason = describe_llm_account_error(exc)
    if user_reason is not None:
        return error_id, f"{user_reason}（错误编号：{error_id}）"
    return str(error_id), str(detail)


@dataclass(frozen=True, slots=True)
class _ExecutionCompleted:
    result: AgentExecutionResult


@dataclass(frozen=True, slots=True)
class _ExecutionFailed:
    exception: BaseException


@dataclass(slots=True)
class _ExecutionState:
    started_at: float
    messages: list[dict]
    effective_tool_names: list[str]
    tool_definitions: list[dict]
    tool_cache: SharedToolCache
    max_tool_context_characters: int
    tool_context_characters: int = 0
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[ToolExecutionSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    termination_reason: str = ""


class AgentExecutor:
    @staticmethod
    def _build_execution_state(
        profile: AgentProfile,
        message: str,
        history: list[AgentMessage] | None,
        allowed_tool_names: Collection[str] | None,
        tool_cache: SharedToolCache | None,
        execution_context: AgentExecutionContext | None,
        max_history_messages: int,
        tool_selection_prompt: str,
    ) -> _ExecutionState:
        effective_tool_names = list(
            profile.tool_names if allowed_tool_names is None else allowed_tool_names
        )
        unexpected_tools = sorted(set(effective_tool_names) - set(profile.tool_names))
        if unexpected_tools:
            raise ValueError(f"Agent {profile.name} 不允许执行工具：{unexpected_tools}")
        return _ExecutionState(
            started_at=time.monotonic(),
            messages=build_messages(
                message,
                history,
                max_history_messages,
                system_prompt=profile.system_prompt,
                tool_selection_prompt=tool_selection_prompt,
                context_length_tokens=(
                    getattr(execution_context.settings, "llm_context_length_tokens", 0)
                    if execution_context is not None
                    else 0
                ),
            ),
            effective_tool_names=effective_tool_names,
            tool_definitions=registry.get_tool_definitions_for(effective_tool_names),
            tool_cache=tool_cache or (
                execution_context.tool_cache if execution_context is not None else SharedToolCache()
            ),
            max_tool_context_characters=(
                execution_context.settings.chat_max_tool_context_characters
                if execution_context is not None
                else get_default_settings().chat_max_tool_context_characters
            ),
        )

    @staticmethod
    def _build_result(
        profile: AgentProfile,
        state: _ExecutionState,
        analysis: str,
        status: Literal["completed", "partial", "failed"],
        reasoning_content: str = "",
        *,
        retryable: bool = True,
    ) -> AgentExecutionResult:
        cleaned_analysis, opinion = parse_opinion_block(
            profile.name,
            profile.display_name,
            analysis,
        )
        result = AgentExecutionResult(
            agent_name=profile.name,
            display_name=profile.display_name,
            analysis=cleaned_analysis,
            opinion=opinion,
            status=status,
            tools_called=state.tools_called,
            tool_results=state.tool_results,
            errors=state.errors,
            warnings=state.warnings,
            duration_ms=int((time.monotonic() - state.started_at) * 1000),
            reasoning_content=reasoning_content,
            retryable=retryable,
            termination_reason=stop_reason(state.termination_reason).code,
        )
        outcome = result.outcome
        return replace(result, status=outcome.status, retryable=retryable and not outcome.reason.fatal,
                       opinion=None if outcome.status == "failed" else result.opinion)

    def _insufficient_evidence_result(self, profile: AgentProfile, state: _ExecutionState) -> AgentExecutionResult:
        state.errors.append("未获取有效工具证据，无法生成可靠结论")
        if state.termination_reason in {"", "stop", "tool_calls"}:
            state.termination_reason = "insufficient_evidence"
        retryable = bool(state.tool_definitions) and (
            not state.tool_results or any(not item.skipped for item in state.tool_results)
        ) and state.termination_reason == "insufficient_evidence"
        return self._build_result(profile, state, "", "failed", retryable=retryable)

    @staticmethod
    def _record_turn_completion(
        state: _ExecutionState, turn: LLMTurn, *, allow_tool_calls: bool = True,
    ) -> None:
        state.termination_reason = model_stop_code(turn.finish_reason)
        warning = completion_warning(
            turn.finish_reason, has_tool_calls=allow_tool_calls and bool(turn.tool_calls),
        )
        if warning and warning not in state.warnings:
            if turn.finish_reason == "length":
                metrics.record_agentic_event("llm_output_truncated")
            elif turn.finish_reason == "stream_error":
                metrics.record_agentic_event("llm_stream_interrupted")
            state.warnings.append(warning)

    async def _execute_tool_calls(
        self,
        profile: AgentProfile,
        state: _ExecutionState,
        tool_calls: list[ToolCallInfo],
        assistant_content: str,
        emit: Callable[[AgentEvent], Awaitable[None]],
        execution_context: AgentExecutionContext | None,
        tool_call_reserve: int,
        capabilities: LLMCapabilities,
        reasoning_content: str = "",
    ) -> None:
        # 必须在拼历史消息、发 tool_call 事件之前拆掉模型多包的参数外壳：
        # 证据、工具缓存键、search policy 统计都直接读 function.arguments，
        # 晚一步解包就会让证据里的 code 变成空串，产业链修复循环据此反复建任务。
        prepared_calls = [prepare_tool_call(tool_call) for tool_call in tool_calls]
        tool_calls = [prepared.call for prepared in prepared_calls]
        prepared_arguments = [prepared.arguments for prepared in prepared_calls]
        # One scoped key per call: grouping, cache lookup, and duplicate backfill
        # all use the same identity instead of re-serializing arguments each time.
        cache_keys = [
            state.tool_cache.cache_key_for_arguments(
                tool_call.function.name, arguments, execution_context
            )
            if arguments is not None
            else state.tool_cache.cache_key_for(tool_call, execution_context)
            for tool_call, arguments in zip(tool_calls, prepared_arguments)
        ]
        assistant_message = build_assistant_tool_message(tool_calls, assistant_content)
        if capabilities.replay_tool_reasoning:
            # Some thinking gateways require the original reasoning on tool turns.
            # This stays in the invocation context; do not log/persist it here.
            replay_reasoning, truncated = _bounded_replay_reasoning(
                reasoning_content, state.max_tool_context_characters
            )
            assistant_message["reasoning_content"] = replay_reasoning
            state.tool_context_characters += len(replay_reasoning)
            if truncated and _REASONING_TRUNCATED_WARNING not in state.warnings:
                state.warnings.append(_REASONING_TRUNCATED_WARNING)
        state.messages.append(assistant_message)
        for tool_call in tool_calls:
            state.tools_called.append(tool_call.function.name)
            await emit(AgentEvent(type="tool_call", tool_call=tool_call))

        settings = execution_context.settings if execution_context is not None else get_default_settings()
        batch_size = settings.chat_max_tool_calls_per_round
        # Keep duplicates with their first occurrence, even across batch boundaries.
        # Side-effecting tools opt out: each request remains a separate execution.
        groups: list[list[int]] = []
        group_by_key: dict[str, list[int]] = {}
        for index, call in enumerate(tool_calls):
            policy = registry.get_tool_policy(call.function.name)
            key = cache_keys[index]
            if (policy is None or policy.deduplicate_in_batch) and key in group_by_key:
                group_by_key[key].append(index)
            else:
                group = [index]
                groups.append(group)
                if policy is None or policy.deduplicate_in_batch:
                    group_by_key[key] = group
        if execution_context is not None and execution_context.reserved_tool_names:
            groups.sort(key=lambda group: tool_calls[group[0]].function.name not in execution_context.reserved_tool_names)
        batches = [sorted(index for group in groups[offset:offset + batch_size] for index in group)
                   for offset in range(0, len(groups), batch_size)]
        messages_start, results_start = len(state.messages), len(state.tool_results)
        completed_indices: list[int] = []
        for number, indices in enumerate(batches, start=1):
            if len(batches) > 1:
                await emit(AgentEvent(type="status", content=(
                    f"本轮 {len(tool_calls)} 个工具请求分批处理：第 {number}/{len(batches)} 批，"
                    f"每批最多 {batch_size} 个新调用；仍受总额度、上下文和时限约束。"
                )))
            await self._execute_tool_batch(
                profile, state, [tool_calls[index] for index in indices],
                [cache_keys[index] for index in indices],
                [prepared_arguments[index] for index in indices], emit,
                execution_context, tool_call_reserve, capabilities,
            )
            completed_indices.extend(indices)
        # Execution may prioritize reads or grouped duplicates; model-visible
        # results and summaries always follow the original assistant call order.
        ordered = sorted(zip(completed_indices, state.messages[messages_start:], state.tool_results[results_start:]))
        state.messages[messages_start:] = [message for _, message, _ in ordered]
        state.tool_results[results_start:] = [result for _, _, result in ordered]

    async def _execute_tool_batch(
        self,
        profile: AgentProfile,
        state: _ExecutionState,
        tool_calls: list[ToolCallInfo],
        cache_keys: list[str],
        prepared_arguments: list[Any | None],
        emit: Callable[[AgentEvent], Awaitable[None]],
        execution_context: AgentExecutionContext | None,
        tool_call_reserve: int,
        capabilities: LLMCapabilities,
    ) -> None:
        tool_results, accepted_calls, rejected_calls = await self._classify_tool_calls(
            state,
            tool_calls,
            cache_keys,
            execution_context=execution_context,
            tool_call_reserve=tool_call_reserve,
        )

        started_reservations: set[int] = set()

        async def execute_accepted(
            call: ToolCallInfo,
            reservation: ToolCallReservation | None,
            cache_key: str,
            arguments: Any | None,
        ) -> tuple[ToolResultInfo, bool]:
            shared = False
            if reservation is not None:
                started_reservations.add(reservation.reservation_id)
            try:
                result, shared = await state.tool_cache.execute_shared(
                    call, allowed_names=state.effective_tool_names,
                    execution_context=execution_context, cache_key=cache_key,
                    arguments=arguments,
                )
                return result, shared
            finally:
                if execution_context is not None and reservation is not None:
                    # Unknown outcome/cancelled work may still run in SharedToolCache;
                    # commit its charge. Refund only confirmed shared outcomes.
                    await wait_for_cleanup(asyncio.create_task(
                        execution_context.settle_tool_reservation(reservation, shared=shared)
                    ))

        tasks: list[asyncio.Task[tuple[ToolResultInfo, bool]]] = []
        try:
            if capabilities.parallel_tool_calls:
                tasks = [
                    asyncio.create_task(
                        execute_accepted(
                            call, reservation, cache_keys[index], prepared_arguments[index]
                        )
                    )
                    for index, call, reservation in accepted_calls
                ]
                accepted_pairs = await asyncio.gather(*tasks)
            else:
                accepted_pairs = []
                for index, call, reservation in accepted_calls:
                    accepted_pairs.append(await execute_accepted(
                        call, reservation, cache_keys[index], prepared_arguments[index]
                    ))
        finally:
            async def settle_unstarted() -> None:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if execution_context is not None:
                    for _, _, reservation in accepted_calls:
                        if reservation is not None and reservation.reservation_id not in started_reservations:
                            await execution_context.refund_tool_reservation(reservation)
            await wait_for_cleanup(asyncio.create_task(settle_unstarted()))
        accepted_results = [result for result, _ in accepted_pairs]
        for (index, tool_call, _), result in zip(accepted_calls, accepted_results):
            tool_results[index] = result
        if execution_context is not None and execution_context.search_policy is not None:
            policy = execution_context.search_policy
            # Cached/coalesced results are evidence, not another execution of a
            # search/read action. Only real completions update discovery pacing.
            completed = [(call, result) for (_, call, _), (result, shared) in zip(accepted_calls, accepted_pairs) if not shared]
            completed.sort(key=lambda pair: pair[0].function.name not in policy.tool_names)
            for call, result in completed:
                policy.observe(call.function.name, call.function.arguments, result.content, is_error=result.is_error)
            policy.finish_batch()
        context_exhausted = state.tool_context_characters >= state.max_tool_context_characters
        # 没真实执行过的调用要能被下游看见：预算拒绝与批内去重都不是「工具成功了」。
        skipped_indices = {index for index, _ in rejected_calls}
        for index, tool_call in rejected_calls:
            if context_exhausted:
                # 与「工具额度不足」区分开：这次不是额度问题，而是结果放不进上下文了。
                metrics.record_agentic_event("tool_context_budget_exhausted")
                tool_results[index] = ToolResultInfo(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    content=serialize_error(
                        "tool_context_budget_exhausted",
                        "本会话的工具结果上下文预算已用尽，本次未执行；"
                        "请直接基于已有信息作答并记录数据缺口，不要再调用工具",
                    ),
                    is_error=False,
                )
                continue
            metrics.record_agentic_event("tool_budget_rejected")
            if _TOOL_BUDGET_WARNING not in state.warnings:
                state.warnings.append(_TOOL_BUDGET_WARNING)
            # Admission captures the exact limiting bucket before concurrent
            # completions/refunds can change the ledger. Keep that snapshot.
            if tool_results[index] is None:
                tool_results[index] = ToolResultInfo(
                    tool_call_id=tool_call.id, name=tool_call.function.name,
                    content=serialize_error("tool_budget_exceeded", budget_rejection_message(None)), is_error=False,
                )
        # 同轮重复调用共享首次调用的真实结果（包括失败和预算拒绝），但保留各自 ID。
        first_indices: dict[str, int] = {}
        for index, tool_call in enumerate(tool_calls):
            key = cache_keys[index]
            first_index = first_indices.setdefault(key, index)
            if tool_results[index] is None and first_index != index:
                skipped_indices.add(index)
                original = tool_results[first_index]
                if original is None:
                    raise RuntimeError("重复工具调用缺少原始结果")
                tool_results[index] = ToolResultInfo(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    content=original.content,
                    is_error=original.is_error,
                )
        resolved_results = [result for result in tool_results if result is not None]
        if len(resolved_results) != len(tool_calls):
            raise RuntimeError("工具调用结果数量与请求不一致")
        context_contents = serialize_context_results(
            [result.content for result in resolved_results],
            state.max_tool_context_characters - state.tool_context_characters,
        )
        for index, (tool_call, result, context_content) in enumerate(
            zip(tool_calls, resolved_results, context_contents)
        ):
            await emit(AgentEvent(type="tool_result", tool_result=result))
            if index in skipped_indices:
                # 被跳过的调用是控制信息而不是证据：即使上下文预算已满也要让模型看到
                # 原因。压缩成空串的话，模型既不知道被拒也不知道被为什么拒，只会
                # 原样再调一次注定被拒的调用。
                context_content = result.content
            evidence_state = EvidenceState.from_content(
                result.content, is_error=result.is_error, context=context_content, skipped=index in skipped_indices,
            )
            state.tool_results.append(
                ToolExecutionSummary(
                    name=tool_call.function.name,
                    is_error=result.is_error,
                    has_evidence=evidence_state.usable_acquisition,
                    context_has_evidence=evidence_state.usable_context,
                    skipped=index in skipped_indices,
                    failure_code=safe_tool_failure_code(result.content),
                )
            )
            if context_content != result.content:
                metrics.record_agentic_event("tool_context_truncated")
                if _TOOL_CONTEXT_WARNING not in state.warnings:
                    state.warnings.append(_TOOL_CONTEXT_WARNING)
            state.tool_context_characters += len(context_content)
            state.messages.append({
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": context_content,
            })
            if result.is_error:
                # 只保留受控短标签：完整 payload 可能很大，且含上游/模型生成的原文，
                # 不适合作为面向用户的 errors 兜底文案。
                state.errors.append(f"{tool_call.function.name}: {tool_failure_label(result.content)}")
            logger.info(
                "Agent %s tool: %s, error=%s",
                profile.name,
                tool_call.function.name,
                result.is_error,
            )

    async def _complete_final_result(
        self,
        profile: AgentProfile,
        state: _ExecutionState,
        llm_client: AsyncLLMClient,
        model: str,
        temperature: float,
        stream_response: bool,
        emit: Callable[[AgentEvent], Awaitable[None]],
        execution_context: AgentExecutionContext,
        *,
        initial_turn: LLMTurn | None = None,
        initial_published: str = "",
    ) -> AgentExecutionResult:
        analysis = ""
        reasoning_content = ""
        retryable = True
        generation_failed = False
        published = initial_published

        async def emit_answer(event: AgentEvent) -> None:
            nonlocal published
            if event.type == "text":
                published += event.content
            await emit(event)

        try:
            turn = initial_turn
            for attempt in range(2):
                if turn is None:
                    if execution_context.deadline_exceeded():
                        raise LLMGenerationTimeoutError("最终分析前请求时限已耗尽")
                    instruction = _FINAL_ANSWER_INSTRUCTION
                    if attempt:
                        instruction += "上一轮未生成有效结论。请纠正为正文结论，不要重复工具调用或获取数据的计划。"
                    turn = await self._complete_turn(
                        llm_client,
                        model=model,
                        messages=[*state.messages, {"role": "user", "content": instruction}],
                        tool_definitions=[],
                        tool_choice="none",
                        temperature=temperature,
                        stream_response=stream_response,
                        emit=emit_answer,
                        max_completion_tokens=execution_context.settings.chat_max_completion_tokens,
                        request_timeout=_llm_request_timeout(execution_context, execution_context.settings),
                    )
                reasoning_content = turn.reasoning_content
                self._record_turn_completion(state, turn, allow_tool_calls=False)
                invalid_tool_output = bool(turn.tool_calls) or has_tool_call_markup(turn.content)
                if invalid_tool_output and _TOOL_MARKUP_WARNING not in state.warnings:
                    state.warnings.append(_TOOL_MARKUP_WARNING)
                analysis = clean_answer(turn.content)
                if analysis:
                    # 已有实质正文时直接保留，不能为修复尾部标记冒险丢掉整份分析。
                    retryable = turn.finish_reason in {None, "stop"} and not invalid_tool_output
                    break
                retryable = False
                if (
                    attempt == 1
                    or turn.finish_reason not in {None, "stop", "tool_calls"}
                    or (not turn.content.strip() and not turn.tool_calls)
                ):
                    # An empty/filtered body must not turn a fatal model finish
                    # into a recoverable empty_response (or hide truncation/EOF).
                    if state.termination_reason in {"stop", "tool_calls"}:
                        state.termination_reason = "invalid_tool_call_output" if invalid_tool_output else "empty_response"
                    state.errors.append(_TOOL_OUTPUT_ERROR if invalid_tool_output else _EMPTY_OUTPUT_ERROR)
                    generation_failed = True
                    break
                warning = "模型未生成有效结论，已尝试一次仅正文纠正"
                if warning not in state.warnings:
                    state.warnings.append(warning)
                metrics.record_agentic_event("agent_final_answer_repair")
                logger.warning("Agent %s 收尾仅包含工具请求或过程描述，进行一次正文纠正", profile.name)
                turn = None
        except asyncio.CancelledError:
            # 正常句子已经逐句送出；保持取消语义，不再请求模型或发布 completed。
            raise
        except Exception as exc:
            analysis = clean_answer(published)
            if isinstance(exc, LLMGenerationTimeoutError):
                if not analysis:
                    raise
                state.termination_reason = "stream_error"
                state.warnings.append("模型生成超时，已保留已生成的有效正文")
            else:
                state.termination_reason = _termination_error_reason(exc)
                _, detail = _log_agent_llm_error(f"Agent {profile.name} 最终分析", exc, "最终分析生成失败")
                state.errors.append(detail)
            generation_failed = not bool(analysis)
            retryable = False

        if stream_response:
            # 非流式 provider/脚本 executor 没有发正文；流式路径只补未发出的部分。
            if analysis and not published.strip():
                await emit(AgentEvent(type="text", content=analysis))
            elif generation_failed:
                await emit(AgentEvent(type="error", error=state.errors[-1] if state.errors else _EMPTY_OUTPUT_ERROR))
        status = result_status(has_output=bool(analysis.strip()), failed=generation_failed,
                               incomplete=bool(state.errors or state.warnings))
        return self._build_result(profile, state, analysis, status, reasoning_content, retryable=retryable)

    async def _complete_turn(
        self,
        llm_client: AsyncLLMClient,
        *,
        model: str,
        messages: list[dict],
        tool_definitions: list[dict],
        tool_choice: ToolChoice,
        temperature: float,
        stream_response: bool,
        emit: Callable[[AgentEvent], Awaitable[None]],
        max_completion_tokens: int | None = None,
        request_timeout: float | None = None,
    ) -> LLMTurn:
        reasoning_source = AgentReasoningSource(block_id=uuid4().hex)
        capabilities = capabilities_from_client(llm_client)
        tool_request = resolve_tool_request(
            tool_definitions,
            tool_choice,
            stream=stream_response,
            capabilities=capabilities,
        )
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": tool_request.stream,
        }
        if tool_request.tools:
            kwargs["tools"] = list(tool_request.tools)
        if tool_request.tool_choice is not None:
            kwargs["tool_choice"] = tool_request.tool_choice

        if not tool_request.stream:
            response = await create_chat_completion(
                llm_client,
                metric_stage=("agent.final@v1" if tool_choice == "none" else "agent.round@v1"),
                max_completion_tokens=max_completion_tokens,
                request_timeout=request_timeout,
                **kwargs,
            )
            turn = normalize_chat_completion(response)
            if turn.reasoning_content:
                await emit(AgentEvent(type="reasoning", content=turn.reasoning_content, reasoning_source=reasoning_source))
            return turn

        normalizer = ChatCompletionStreamNormalizer()
        stream_text_immediately = tool_choice == "none"
        # 正文按句过滤后推送：工具标记和获取数据的过程描述不能进入不可撤回的流。
        markup_filter = AnswerTextStream() if stream_text_immediately else None

        async def flush_markup() -> None:
            if markup_filter is None:
                return
            tail = markup_filter.flush()
            if tail:
                await emit(AgentEvent(type="text", content=tail))

        stream = stream_chat_completion(
            llm_client,
            metric_stage=("agent.final@v1" if tool_choice == "none" else "agent.round@v1"),
            max_completion_tokens=max_completion_tokens,
            request_timeout=request_timeout,
            **kwargs,
        )
        try:
            async with aclosing(stream):
                async for chunk in stream:
                    delta = normalizer.add(chunk)
                    if delta.content:
                        if stream_text_immediately:
                            text = markup_filter.feed(delta.content) if markup_filter else delta.content
                            if text:
                                await emit(AgentEvent(type="text", content=text))
                    if delta.reasoning_content:
                        await emit(
                            AgentEvent(type="reasoning", content=delta.reasoning_content, reasoning_source=reasoning_source)
                        )
        except asyncio.CancelledError:
            await flush_markup()
            raise
        except (LLMRetryableError, LLMGenerationTimeoutError, TimeoutError):
            await flush_markup()
            turn = normalizer.finish()
            if not clean_answer(turn.content):
                raise
            return LLMTurn(
                content=turn.content,
                reasoning_content=turn.reasoning_content,
                tool_calls=(),
                finish_reason="stream_error",
            )

        await flush_markup()
        turn = normalizer.finish()
        if turn.finish_reason is None:
            # Clean transport EOF is not a model completion. Never execute tool
            # arguments from a stream whose terminal frame was not received.
            return LLMTurn(turn.content, turn.reasoning_content, (), finish_reason="stream_error")
        return turn

    async def _classify_tool_calls(
        self,
        state: _ExecutionState,
        tool_calls: list[ToolCallInfo],
        cache_keys: list[str],
        *,
        execution_context: AgentExecutionContext | None,
        tool_call_reserve: int,
    ) -> tuple[list[ToolResultInfo | None], list[tuple[int, ToolCallInfo, ToolCallReservation | None]], list[tuple[int, ToolCallInfo]]]:
        """按策略分类：有效缓存重放 / 同批合并 / 按预算执行。"""
        tool_results: list[ToolResultInfo | None] = [None] * len(tool_calls)
        unique_calls: list[tuple[int, ToolCallInfo]] = []
        batch_keys: set[str] = set()
        for index, tool_call in enumerate(tool_calls):
            cache_key = cache_keys[index]
            policy = registry.get_tool_policy(tool_call.function.name)
            deduplicate = policy is None or policy.deduplicate_in_batch
            if deduplicate and cache_key in batch_keys:
                metrics.record_agentic_event("duplicate_tool_call")
                continue  # 执行结束后回填本轮首次调用结果，不额外消耗预算。
            batch_keys.add(cache_key)
            previous = state.tool_cache.get_cached_result(
                tool_call,
                allowed_names=state.effective_tool_names,
                execution_context=execution_context,
                cache_key=cache_key,
            )
            if previous is not None:
                tool_results[index] = previous
                continue
            unique_calls.append((index, tool_call))

        accepted_calls: list[tuple[int, ToolCallInfo, ToolCallReservation | None]] = []
        rejected_calls: list[tuple[int, ToolCallInfo]] = []
        # Prefer body reads within a model batch, but preserve result order by original index.
        if execution_context is not None and execution_context.reserved_tool_names:
            unique_calls.sort(key=lambda pair: pair[1].function.name not in execution_context.reserved_tool_names)
        # 上下文预算耗尽后不再执行工具：跑了也只会因为 tool_context_characters 已经
        # 用满而被整条挤掉（serialize_context_results 的 allowance 变 0），模型看不到
        # 任何结果，工具配额和 LLM 往返却照常消耗。
        context_exhausted = state.tool_context_characters >= state.max_tool_context_characters
        if context_exhausted and unique_calls:
            metrics.record_agentic_event("tool_context_budget_exhausted")
            if _TOOL_CONTEXT_WARNING not in state.warnings:
                state.warnings.append(_TOOL_CONTEXT_WARNING)
        for index, tool_call in unique_calls:
            allowed = not context_exhausted
            reservation = None
            if allowed and execution_context is not None:
                reservation, rejection = await execution_context.reserve_tool_call_with_diagnostics(
                    preserve=tool_call_reserve, tool_name=tool_call.function.name,
                )
                allowed = reservation is not None
                if rejection is not None:
                    tool_results[index] = ToolResultInfo(
                        tool_call_id=tool_call.id, name=tool_call.function.name,
                        content=serialize_error("tool_budget_exceeded", budget_rejection_message(rejection),
                                                data={"budget": rejection}),
                        is_error=False,
                    )
            if allowed:
                accepted_calls.append((index, tool_call, reservation))
            else:
                rejected_calls.append((index, tool_call))
        return tool_results, accepted_calls, rejected_calls

    async def run(
        self,
        profile: AgentProfile,
        message: str,
        history: list[AgentMessage] | None,
        llm_client: AsyncLLMClient,
        model: str,
        event_queue: asyncio.Queue | None = None,
        tool_cache: "SharedToolCache | None" = None,
        execution_context: AgentExecutionContext | None = None,
        allowed_tool_names: Collection[str] | None = None,
        temperature: float = 0.1,
        tool_selection_prompt: str = "",
        max_history_messages: int = 10,
        require_tool_first_round: bool = True,
        require_tool_evidence: bool = False,
        stream_response: bool = False,
        tool_call_reserve: int = 0,
        task_id: str | None = None,
        attempt: int = 1,
    ) -> AgentExecutionResult:
        """使用统一执行引擎运行一个 AgentProfile。

        Param:
            message: 用户消息
            history: 历史消息列表，可选
            llm_client: Provider 无关的异步 Chat Completions 客户端
            model: 模型名称
            event_queue: 可选事件队列，用于实时推送工具调用/结果增量
            tool_cache: 可选的跨 Agent 共享工具缓存，未提供时本 Agent 内部新建（仅本 Agent 内去重）
        Return:
            AgentExecutionResult，包含最终分析文本、调用过的工具和耗时
        """
        execution_context = execution_context or AgentExecutionContext.from_current(
            get_default_settings()
        )
        capabilities = capabilities_from_client(llm_client)
        state = self._build_execution_state(
            profile,
            message,
            history,
            allowed_tool_names,
            tool_cache,
            execution_context,
            max_history_messages,
            tool_selection_prompt,
        )

        turn_number = 1

        async def emit(delta: AgentEvent) -> None:
            if event_queue is not None:
                if delta.type == "reasoning" and delta.reasoning_source is not None:
                    delta = delta.model_copy(update={
                        "reasoning_source": delta.reasoning_source.model_copy(update={
                            "source": profile.display_name, "turn": turn_number,
                            "task_id": task_id, "attempt": attempt,
                        }),
                    })
                await event_queue.put(delta)

        published_text = ""

        async def emit_pending(event: AgentEvent) -> None:
            nonlocal published_text
            if event.type == "text":
                if require_tool_evidence and not any(item.evidence_state.usable_context for item in state.tool_results):
                    return
                published_text += event.content
            await emit(event)

        forced_tool_round = False
        search_guidance_message = None
        for round_num in range(profile.max_rounds):
            turn_number = round_num + 1
            metrics.record_agentic_event("agent_round")
            tool_definitions = state.tool_definitions
            if execution_context.search_policy is not None:
                guidance = execution_context.search_policy.instruction()
                # One replaceable message per inner run, not an ever-growing instruction history.
                if search_guidance_message is None:
                    search_guidance_message = {"role": "user", "content": guidance}
                    state.messages.append(search_guidance_message)
                else:
                    search_guidance_message["content"] = guidance
            if execution_context.reserved_tool_names:
                tool_definitions = [definition for definition in tool_definitions if execution_context.tool_calls_available(
                    preserve=tool_call_reserve, tool_name=definition["function"]["name"],
                ) > 0]
            if (
                tool_definitions
                and execution_context.tool_calls_available(preserve=tool_call_reserve) <= 0
            ):
                tool_definitions = []
                if _TOOL_BUDGET_WARNING not in state.warnings:
                    state.warnings.append(_TOOL_BUDGET_WARNING)
            if (
                tool_definitions
                and state.tool_context_characters >= state.max_tool_context_characters
            ):
                # 工具结果的上下文预算已满：再执行也只会被 _classify_tool_calls 整批拒绝，
                # 白烧一轮 LLM 往返，而模型因为看得见工具，宁可再调一次也不肯作答
                # （真实事故：用户看到「上下文预算不足」之后就没有任何输出）。收走工具
                # 定义，逼它用已有证据收敛——这本就是预算耗尽时对模型的既有要求。
                tool_definitions = []
                if _TOOL_CONTEXT_WARNING not in state.warnings:
                    state.warnings.append(_TOOL_CONTEXT_WARNING)
            tool_choice: ToolChoice = (
                "required"
                if tool_definitions
                and (forced_tool_round or (round_num == 0 and require_tool_first_round))
                else "auto"
                if tool_definitions
                else "none"
            )
            try:
                turn = await self._complete_turn(
                    llm_client,
                    model=model,
                    messages=(
                        [*state.messages, {"role": "user", "content": _FINAL_ANSWER_INSTRUCTION}]
                        if tool_choice == "none" else state.messages
                    ),
                    tool_definitions=tool_definitions,
                    tool_choice=tool_choice,
                    temperature=temperature,
                    stream_response=stream_response,
                    emit=emit_pending,
                    max_completion_tokens=(
                        execution_context.settings.chat_max_completion_tokens
                    ),
                    request_timeout=_llm_request_timeout(
                        execution_context, execution_context.settings
                    ),
                )
            except Exception as exc:
                state.termination_reason = _termination_error_reason(exc)
                _, detail = _log_agent_llm_error(
                    f"Agent {profile.name} 模型调用",
                    exc,
                    "模型调用失败",
                )
                if require_tool_evidence and not any(item.evidence_state.usable_context for item in state.tool_results):
                    if isinstance(exc, LLMGenerationTimeoutError):
                        state.termination_reason = "generation_timeout"
                    state.errors.append(detail)
                    return self._insufficient_evidence_result(profile, state)
                if isinstance(exc, LLMGenerationTimeoutError):
                    raise
                if is_llm_connection_error(exc):
                    # LLM 网关不可达是可重试的上游故障：快速失败并保留真实原因，
                    # 继续空转只会把根因伪装成"调研证据不足"误导排查与监控。
                    raise UpstreamUnavailableError(
                        "LLM 服务连接失败，请检查网络或代理配置后重试"
                    ) from exc
                state.errors.append(detail)
                if isinstance(exc, LLMInvalidResponseError):
                    if stream_response:
                        await emit(AgentEvent(type="error", error=detail))
                    return self._build_result(
                        profile,
                        state,
                        detail,
                        "failed",
                        retryable=False,
                    )
                if stream_response:
                    await emit(AgentEvent(type="error", error=detail))
                    return self._build_result(profile, state, "", "failed", retryable=False)
                return self._build_result(profile, state, detail, "failed", retryable=False)

            self._record_turn_completion(state, turn)

            if (
                tool_choice == "none"
                or turn.finish_reason == "stream_error"
            ):
                if require_tool_evidence and not any(result.evidence_state.usable_context for result in state.tool_results):
                    return self._insufficient_evidence_result(profile, state)
                return await self._complete_final_result(
                    profile, state, llm_client, model, temperature, stream_response, emit,
                    execution_context, initial_turn=turn, initial_published=published_text,
                )

            tool_calls = list(turn.tool_calls)
            if not tool_calls and tool_definitions:
                tool_calls = extract_pseudo_tool_calls(
                    turn.content,
                    registry,
                    allowed_names=state.effective_tool_names,
                )
            if not tool_calls:
                # 没被执行（方言不认识、或工具已被预算收走）的标记绝不能当结论给用户：
                # 真实事故里用户收到的「回答」是一串 <｜DSML｜invoke ...>。
                answer_text = strip_tool_call_markup(turn.content or "")
                if answer_text != (turn.content or "") and _TOOL_MARKUP_WARNING not in state.warnings:
                    state.warnings.append(_TOOL_MARKUP_WARNING)
                if (
                    tool_definitions
                    and require_tool_evidence
                    and not any(result.evidence_state.usable_context for result in state.tool_results)
                    and not forced_tool_round
                ):
                    # 部分模型在 auto 模式下只叙述"正在调用工具"而不真正发起
                    # tool_calls；补一轮强制要求调用工具，仍失败才按无证据处理。
                    forced_tool_round = True
                    continue
                if require_tool_evidence and not any(
                    result.evidence_state.usable_context for result in state.tool_results
                ):
                    return self._insufficient_evidence_result(profile, state)
                return await self._complete_final_result(
                    profile, state, llm_client, model, temperature, stream_response, emit,
                    execution_context, initial_turn=turn, initial_published=published_text,
                )

            await self._execute_tool_calls(
                profile,
                state,
                tool_calls,
                turn.content,
                emit,
                execution_context,
                tool_call_reserve,
                capabilities,
                turn.reasoning_content,
            )

        if require_tool_evidence and not any(
            result.evidence_state.usable_context for result in state.tool_results
        ):
            return self._insufficient_evidence_result(profile, state)

        turn_number += 1
        return await self._complete_final_result(
            profile,
            state,
            llm_client,
            model,
            temperature,
            stream_response,
            emit,
            execution_context,
        )

    async def stream(
        self,
        profile: AgentProfile,
        message: str,
        history: list[AgentMessage] | None,
        llm_client: AsyncLLMClient,
        model: str,
        *,
        allowed_tool_names: Collection[str] | None = None,
        temperature: float = 0.1,
        tool_selection_prompt: str = "",
        max_history_messages: int = 10,
        require_tool_first_round: bool = False,
        require_tool_evidence: bool = False,
        execution_context: AgentExecutionContext | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        queue: asyncio.Queue[AgentEvent | _ExecutionCompleted | _ExecutionFailed]
        queue = asyncio.Queue()

        async def execute() -> None:
            try:
                result = await self.run(
                    profile,
                    message,
                    history,
                    llm_client,
                    model,
                    event_queue=queue,
                    allowed_tool_names=allowed_tool_names,
                    temperature=temperature,
                    tool_selection_prompt=tool_selection_prompt,
                    max_history_messages=max_history_messages,
                    require_tool_first_round=require_tool_first_round,
                    require_tool_evidence=require_tool_evidence,
                    execution_context=execution_context,
                    stream_response=True,
                )
                await queue.put(_ExecutionCompleted(result))
            except BaseException as exc:
                await queue.put(_ExecutionFailed(exc))

        execution_task = asyncio.create_task(execute())
        try:
            while True:
                event = await queue.get()
                if isinstance(event, _ExecutionFailed):
                    raise event.exception
                if isinstance(event, _ExecutionCompleted):
                    if event.result.status == "failed" and not event.result.analysis.strip() and (
                        event.result.termination_reason == "insufficient_evidence"
                        or "未获取有效工具证据，无法生成可靠结论" in event.result.errors
                    ):
                        yield AgentEvent(type="text", content=build_evidence_gap_report([event.result]))
                    yield AgentEvent(
                        type="done",
                        reasoning_content=event.result.reasoning_content or None,
                        status=event.result.outcome.status,
                        warnings=event.result.warnings,
                    )
                    break
                yield event
        finally:
            if not execution_task.done():
                execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)


agent_executor = AgentExecutor()
