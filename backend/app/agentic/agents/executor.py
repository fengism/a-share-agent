from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Collection
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Literal
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
from app.agentic.runtime.completion import completion_warning
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.runtime.llm import create_chat_completion, stream_chat_completion
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.calls import (
    build_assistant_tool_message,
    extract_pseudo_tool_calls,
)
from app.agentic.tools.serialization import (
    has_meaningful_tool_content,
    serialize_context_results,
    serialize_error,
    tool_call_cache_key,
)
from app.configuration import get_settings
from app.core.errors import build_internal_error, log_internal_error
from app.core.exceptions import UpstreamUnavailableError
from app.core.metrics import metrics
from app.infrastructure.llm.adapters import LLMInvalidResponseError, LLMRetryableError
from app.infrastructure.llm.policy import LLMGenerationTimeoutError
from app.infrastructure.llm.runtime import describe_llm_account_error, is_llm_connection_error
from app.infrastructure.llm.tool_calling import (
    AsyncLLMClient,
    ChatCompletionStreamNormalizer,
    LLMCapabilities,
    LLMTurn,
    ToolChoice,
    capabilities_from_client,
    normalize_chat_completion,
    resolve_tool_request,
)

logger = logging.getLogger(__name__)
_EMPTY_OUTPUT_ERROR = "模型未生成有效回答，请稍后重试"
_TOOL_CONTEXT_WARNING = "工具上下文预算不足，部分证据已截断或未提供给模型，结论可能受限"
_TOOL_BUDGET_WARNING = "部分工具请求受单批/总额度、搜索节奏或正文预留限制，已拒绝超额请求；请以剩余额度为准"


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
            ),
            effective_tool_names=effective_tool_names,
            tool_definitions=registry.get_tool_definitions_for(effective_tool_names),
            tool_cache=tool_cache or (
                execution_context.tool_cache if execution_context is not None else SharedToolCache()
            ),
            max_tool_context_characters=(
                execution_context.settings.chat_max_tool_context_characters
                if execution_context is not None
                else get_settings().chat_max_tool_context_characters
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
        return AgentExecutionResult(
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
            termination_reason=state.termination_reason,
        )

    @staticmethod
    def _record_turn_completion(
        state: _ExecutionState, turn: LLMTurn, *, allow_tool_calls: bool = True,
    ) -> None:
        state.termination_reason = turn.finish_reason if turn.finish_reason in {
            "stop", "tool_calls", "length", "content_filter", "stream_error",
        } else "stop" if turn.finish_reason is None else "unexpected_finish"
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
        assistant_message = build_assistant_tool_message(tool_calls, assistant_content)
        if capabilities.replay_tool_reasoning:
            # Some thinking gateways require the original reasoning on tool turns.
            # This stays in the invocation context; do not log/persist it here.
            assistant_message["reasoning_content"] = reasoning_content
        state.messages.append(assistant_message)
        for tool_call in tool_calls:
            state.tools_called.append(tool_call.function.name)
            await emit(AgentEvent(type="tool_call", tool_call=tool_call))

        tool_results, accepted_calls, rejected_calls = await self._classify_tool_calls(
            state,
            tool_calls,
            execution_context=execution_context,
            tool_call_reserve=tool_call_reserve,
        )

        if capabilities.parallel_tool_calls:
            accepted_results = await asyncio.gather(
                *(
                    state.tool_cache.execute(
                        tool_call,
                        allowed_names=state.effective_tool_names,
                        execution_context=execution_context,
                    )
                    for _, tool_call in accepted_calls
                )
            )
        else:
            accepted_results = []
            for _, tool_call in accepted_calls:
                accepted_results.append(
                    await state.tool_cache.execute(
                        tool_call,
                        allowed_names=state.effective_tool_names,
                        execution_context=execution_context,
                    )
                )
        for (index, tool_call), result in zip(accepted_calls, accepted_results):
            tool_results[index] = result
        if execution_context is not None and execution_context.search_policy is not None:
            policy = execution_context.search_policy
            # Process discovery completions first, then reads in this batch; no reset on reservations.
            completed = list(zip(accepted_calls, accepted_results))
            completed.sort(key=lambda pair: pair[0][1].function.name not in policy.tool_names)
            for (_, call), result in completed:
                policy.observe(call.function.name, call.function.arguments, result.content, is_error=result.is_error)
            policy.finish_batch()
        for index, tool_call in rejected_calls:
            metrics.record_agentic_event("tool_budget_rejected")
            if _TOOL_BUDGET_WARNING not in state.warnings:
                state.warnings.append(_TOOL_BUDGET_WARNING)
            tool_results[index] = ToolResultInfo(
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
                content=serialize_error(
                    "tool_budget_exceeded",
                    "本批次或总额度不足，或触及搜索节奏/正文预留限制；请优先读取已发现的网页/PDF正文，不要原样重复被拒调用",
                ),
                is_error=False,
            )
        # 同轮重复调用共享首次调用的真实结果（包括失败和预算拒绝），但保留各自 ID。
        first_indices: dict[str, int] = {}
        for index, tool_call in enumerate(tool_calls):
            key = tool_call_cache_key(tool_call)
            first_index = first_indices.setdefault(key, index)
            if tool_results[index] is None and first_index != index:
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
        for tool_call, result, context_content in zip(tool_calls, resolved_results, context_contents):
            await emit(AgentEvent(type="tool_result", tool_result=result))
            has_evidence = (
                not result.is_error
                and has_meaningful_tool_content(result.content)
            )
            state.tool_results.append(
                ToolExecutionSummary(
                    name=tool_call.function.name,
                    is_error=result.is_error,
                    has_evidence=has_evidence,
                    context_has_evidence=(
                        has_evidence and has_meaningful_tool_content(context_content)
                    ),
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
                state.errors.append(f"{tool_call.function.name}: {result.content}")
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
    ) -> AgentExecutionResult:
        generation_failed = False
        retryable = True
        reasoning_content = ""
        try:
            turn = await self._complete_turn(
                llm_client,
                model=model,
                messages=state.messages,
                tool_definitions=state.tool_definitions,
                tool_choice="none",
                temperature=temperature,
                stream_response=stream_response,
                emit=emit,
                max_completion_tokens=(
                    execution_context.settings.chat_max_completion_tokens
                ),
            )
            analysis = turn.content
            reasoning_content = turn.reasoning_content
            self._record_turn_completion(state, turn, allow_tool_calls=False)
            retryable = bool(analysis.strip()) and turn.finish_reason in {None, "stop"}
        except Exception as exc:
            if isinstance(exc, LLMGenerationTimeoutError):
                raise
            state.termination_reason = _termination_error_reason(exc)
            generation_failed = True
            retryable = False  # Transport owns model retries; Reviewer must not replay them.
            _, analysis = _log_agent_llm_error(
                f"Agent {profile.name} 最终分析",
                exc,
                "最终分析生成失败",
            )
            state.errors.append(analysis)
            if stream_response:
                await emit(AgentEvent(type="error", error=analysis))

        if not generation_failed and not analysis.strip():
            if state.termination_reason == "stop":
                state.termination_reason = "empty_response"
            state.errors.append(_EMPTY_OUTPUT_ERROR)
            if stream_response:
                await emit(AgentEvent(type="error", error=_EMPTY_OUTPUT_ERROR))

        status: Literal["completed", "partial", "failed"]
        if generation_failed or not analysis.strip():
            status = "failed"
        elif state.errors or state.warnings:
            status = "partial"
        else:
            status = "completed"
        return self._build_result(
            profile,
            state,
            analysis,
            status,
            reasoning_content,
            retryable=retryable,
        )

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
                **kwargs,
            )
            turn = normalize_chat_completion(response)
            if turn.reasoning_content:
                await emit(AgentEvent(type="reasoning", content=turn.reasoning_content, reasoning_source=reasoning_source))
            return turn

        normalizer = ChatCompletionStreamNormalizer()
        stream_text_immediately = tool_choice == "none"
        stream = stream_chat_completion(
            llm_client,
            metric_stage=("agent.final@v1" if tool_choice == "none" else "agent.round@v1"),
            max_completion_tokens=max_completion_tokens,
            **kwargs,
        )
        try:
            async with aclosing(stream):
                async for chunk in stream:
                    delta = normalizer.add(chunk)
                    if delta.content:
                        if stream_text_immediately:
                            await emit(AgentEvent(type="text", content=delta.content))
                    if delta.reasoning_content:
                        await emit(
                            AgentEvent(type="reasoning", content=delta.reasoning_content, reasoning_source=reasoning_source)
                        )
        except LLMRetryableError:
            turn = normalizer.finish()
            if not turn.content.strip():
                raise
            return LLMTurn(
                content=turn.content,
                reasoning_content=turn.reasoning_content,
                tool_calls=(),
                finish_reason="stream_error",
            )

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
        *,
        execution_context: AgentExecutionContext | None,
        tool_call_reserve: int,
    ) -> tuple[list[ToolResultInfo | None], list[tuple[int, ToolCallInfo]], list[tuple[int, ToolCallInfo]]]:
        """按策略分类：有效缓存重放 / 同批合并 / 按预算执行。"""
        settings = (
            execution_context.settings
            if execution_context is not None
            else get_settings()
        )
        tool_results: list[ToolResultInfo | None] = [None] * len(tool_calls)
        unique_calls: list[tuple[int, ToolCallInfo]] = []
        batch_keys: set[str] = set()
        for index, tool_call in enumerate(tool_calls):
            cache_key = tool_call_cache_key(tool_call)
            policy = registry.get_tool_policy(tool_call.function.name)
            deduplicate = policy is None or policy.deduplicate_in_batch
            if deduplicate and cache_key in batch_keys:
                metrics.record_agentic_event("duplicate_tool_call")
                continue  # 执行结束后回填本轮首次调用结果，不额外消耗预算。
            batch_keys.add(cache_key)
            previous = state.tool_cache.get_cached_result(
                tool_call, allowed_names=state.effective_tool_names,
            )
            if previous is not None:
                tool_results[index] = previous
                continue
            unique_calls.append((index, tool_call))

        accepted_calls: list[tuple[int, ToolCallInfo]] = []
        rejected_calls: list[tuple[int, ToolCallInfo]] = []
        # Prefer body reads within a model batch, but preserve result order by original index.
        if execution_context is not None and execution_context.reserved_tool_names:
            unique_calls.sort(key=lambda pair: pair[1].function.name not in execution_context.reserved_tool_names)
        for index, tool_call in unique_calls:
            allowed = len(accepted_calls) < settings.chat_max_tool_calls_per_round
            if allowed and execution_context is not None:
                allowed = bool(await execution_context.reserve_tool_calls(
                    1, preserve=tool_call_reserve, tool_name=tool_call.function.name,
                ))
            (accepted_calls if allowed else rejected_calls).append((index, tool_call))
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
            get_settings()
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
                    messages=state.messages,
                    tool_definitions=tool_definitions,
                    tool_choice=tool_choice,
                    temperature=temperature,
                    stream_response=stream_response,
                    emit=emit,
                    max_completion_tokens=(
                        execution_context.settings.chat_max_completion_tokens
                    ),
                )
            except Exception as exc:
                state.termination_reason = _termination_error_reason(exc)
                _, detail = _log_agent_llm_error(
                    f"Agent {profile.name} 模型调用",
                    exc,
                    "模型调用失败",
                )
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

            if turn.finish_reason == "stream_error":
                if stream_response and turn.content and tool_choice != "none":
                    await emit(AgentEvent(type="text", content=turn.content))
                return self._build_result(
                    profile, state, turn.content,
                    "partial" if turn.content.strip() else "failed",
                    turn.reasoning_content,
                    retryable=False,
                )

            tool_calls = list(turn.tool_calls)
            if not tool_calls and tool_definitions:
                tool_calls = extract_pseudo_tool_calls(
                    turn.content,
                    registry,
                    allowed_names=state.effective_tool_names,
                )
            if not tool_calls:
                if (
                    tool_definitions
                    and require_tool_evidence
                    and not any(result.context_has_evidence for result in state.tool_results)
                    and not forced_tool_round
                ):
                    # 部分模型在 auto 模式下只叙述"正在调用工具"而不真正发起
                    # tool_calls；补一轮强制要求调用工具，仍失败才按无证据处理。
                    forced_tool_round = True
                    continue
                if require_tool_evidence and not any(
                    result.context_has_evidence for result in state.tool_results
                ):
                    detail = "未获取有效工具证据，无法生成可靠结论"
                    state.errors.append(detail)
                    if stream_response:
                        await emit(AgentEvent(type="error", error=detail))
                    return self._build_result(profile, state, "", "failed", turn.reasoning_content)
                if not turn.content.strip():
                    if state.termination_reason == "stop":
                        state.termination_reason = "empty_response"
                    state.errors.append(_EMPTY_OUTPUT_ERROR)
                    if stream_response:
                        await emit(AgentEvent(type="error", error=_EMPTY_OUTPUT_ERROR))
                    return self._build_result(
                        profile,
                        state,
                        "",
                        "failed",
                        turn.reasoning_content,
                        retryable=False,
                    )
                if stream_response and turn.content and tool_choice != "none":
                    await emit(AgentEvent(type="text", content=turn.content))
                return self._build_result(
                    profile,
                    state,
                    turn.content,
                    "partial" if state.errors or state.warnings else "completed",
                    turn.reasoning_content,
                    retryable=turn.finish_reason in {None, "stop"},
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
            result.context_has_evidence for result in state.tool_results
        ):
            detail = "未获取有效工具证据，无法生成可靠结论"
            state.errors.append(detail)
            if stream_response:
                await emit(AgentEvent(type="error", error=detail))
            return self._build_result(profile, state, "", "failed")

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
                    yield AgentEvent(
                        type="done",
                        reasoning_content=event.result.reasoning_content or None,
                        status=event.result.status,
                        warnings=event.result.warnings,
                    )
                    break
                yield event
        finally:
            if not execution_task.done():
                execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)


agent_executor = AgentExecutor()
