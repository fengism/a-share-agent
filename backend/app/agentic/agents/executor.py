from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Collection
from dataclasses import dataclass, field
from typing import Literal

from openai import AsyncOpenAI

from app.agentic.agents.contracts import (
    AgentExecutionResult,
    AgentProfile,
    ToolExecutionSummary,
)
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.messages import build_messages
from app.agentic.orchestration.opinions import parse_opinion_block
from app.agentic.protocol import (
    AgentMessage,
    ToolCallFunction,
    ToolCallInfo,
    ToolResultInfo,
)
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.runtime.llm import create_chat_completion, stream_chat_completion
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.calls import (
    build_assistant_tool_message,
    extract_pseudo_tool_calls,
    tool_call_infos_from_stream,
)
from app.agentic.tools.serialization import (
    has_meaningful_tool_content,
    serialize_context_result,
    serialize_error,
    tool_call_cache_key,
)
from app.configuration import get_settings
from app.core.errors import build_internal_error, log_internal_error
from app.core.exceptions import UpstreamUnavailableError
from app.core.metrics import metrics
from app.infrastructure.llm.adapters import LLMRetryableError
from app.infrastructure.llm.runtime import describe_llm_account_error, is_llm_connection_error

logger = logging.getLogger(__name__)
_OUTPUT_TRUNCATED_WARNING = "模型输出达到长度上限，回答可能不完整"
_EMPTY_OUTPUT_ERROR = "模型未生成有效回答，请稍后重试"
_STREAM_INTERRUPTED_WARNING = "模型流式响应中断，已保留已生成内容"
_TOOL_BUDGET_WARNING = "工具调用额度已用尽，已基于现有结果继续分析"


def _log_agent_llm_error(operation: str, exc: Exception, public_message: str) -> tuple[str, str]:
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
class _AgentTurn:
    content: str
    reasoning_content: str
    tool_calls: tuple[ToolCallInfo, ...]
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _ExecutionCompleted:
    result: AgentExecutionResult


@dataclass(frozen=True, slots=True)
class _ExecutionFailed:
    exception: BaseException


@dataclass
class ToolCallDedupe:
    """跨轮次共享的工具调用去重登记（由调研 session 持有）。

    同一次自适应多轮调研中，后续轮次重发的相同"工具+参数"调用会重放
    先前成功结果，而不是重新打上游。
    """

    seen_keys: set[str] = field(default_factory=set)
    succeeded: dict[str, ToolResultInfo] = field(default_factory=dict)


@dataclass(slots=True)
class _ExecutionState:
    started_at: float
    messages: list[dict]
    effective_tool_names: list[str]
    tool_definitions: list[dict]
    tool_cache: SharedToolCache
    max_tool_context_characters: int
    tool_context_characters: int = 0
    seen_tool_call_keys: set[str] = field(default_factory=set)
    succeeded_tool_results: dict[str, ToolResultInfo] = field(default_factory=dict)
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[ToolExecutionSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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
        tool_dedupe: ToolCallDedupe | None = None,
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
            seen_tool_call_keys=(
                tool_dedupe.seen_keys if tool_dedupe is not None else set()
            ),
            succeeded_tool_results=(
                tool_dedupe.succeeded if tool_dedupe is not None else {}
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
        )

    @staticmethod
    def _record_turn_completion(state: _ExecutionState, turn: _AgentTurn) -> None:
        if (
            turn.finish_reason == "length"
            and _OUTPUT_TRUNCATED_WARNING not in state.warnings
        ):
            metrics.record_agentic_event("llm_output_truncated")
            state.warnings.append(_OUTPUT_TRUNCATED_WARNING)
        if (
            turn.finish_reason == "stream_error"
            and _STREAM_INTERRUPTED_WARNING not in state.warnings
        ):
            metrics.record_agentic_event("llm_stream_interrupted")
            state.warnings.append(_STREAM_INTERRUPTED_WARNING)

    async def _execute_tool_calls(
        self,
        profile: AgentProfile,
        state: _ExecutionState,
        tool_calls: list[ToolCallInfo],
        assistant_content: str,
        emit: Callable[[AgentEvent], Awaitable[None]],
        execution_context: AgentExecutionContext | None,
        tool_call_reserve: int,
    ) -> None:
        state.messages.append(build_assistant_tool_message(tool_calls, assistant_content))
        for tool_call in tool_calls:
            state.tools_called.append(tool_call.function.name)
            await emit(AgentEvent(type="tool_call", tool_call=tool_call))

        tool_results, accepted_calls, rejected_calls = await self._classify_tool_calls(
            state,
            tool_calls,
            execution_context=execution_context,
            tool_call_reserve=tool_call_reserve,
        )

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
        for (index, tool_call), result in zip(accepted_calls, accepted_results):
            tool_results[index] = result
            if result.is_error:
                # 失败调用解除去重标记：上游瞬时可导致失败，相同参数应允许重试
                state.seen_tool_call_keys.discard(tool_call_cache_key(tool_call))
            else:
                state.succeeded_tool_results[tool_call_cache_key(tool_call)] = result
        for index, tool_call in rejected_calls:
            metrics.record_agentic_event("tool_budget_rejected")
            if _TOOL_BUDGET_WARNING not in state.warnings:
                state.warnings.append(_TOOL_BUDGET_WARNING)
            tool_results[index] = ToolResultInfo(
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
                content=serialize_error(
                    "tool_budget_exceeded",
                    "本轮或本次请求的工具调用预算已用尽，请基于已有结果完成回答",
                ),
                is_error=False,
            )
        resolved_results = [result for result in tool_results if result is not None]
        if len(resolved_results) != len(tool_calls):
            raise RuntimeError("工具调用结果数量与请求不一致")
        for tool_call, result in zip(tool_calls, resolved_results):
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
                )
            )
            remaining_context = max(
                0,
                state.max_tool_context_characters - state.tool_context_characters,
            )
            context_content = serialize_context_result(
                result.content,
                remaining_context,
            )
            if context_content != result.content:
                metrics.record_agentic_event("tool_context_truncated")
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
        llm_client: AsyncOpenAI,
        model: str,
        temperature: float,
        stream_response: bool,
        emit: Callable[[AgentEvent], Awaitable[None]],
        execution_context: AgentExecutionContext,
    ) -> AgentExecutionResult:
        generation_failed = False
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
            self._record_turn_completion(state, turn)
        except Exception as exc:
            generation_failed = True
            _, analysis = _log_agent_llm_error(
                f"Agent {profile.name} 最终分析",
                exc,
                "最终分析生成失败",
            )
            state.errors.append(analysis)
            if stream_response:
                await emit(AgentEvent(type="error", error=analysis))

        if not generation_failed and not analysis.strip():
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
        )

    async def _complete_turn(
        self,
        llm_client: AsyncOpenAI,
        *,
        model: str,
        messages: list[dict],
        tool_definitions: list[dict],
        tool_choice: str,
        temperature: float,
        stream_response: bool,
        emit: Callable[[AgentEvent], Awaitable[None]],
        max_completion_tokens: int | None = None,
    ) -> _AgentTurn:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream_response,
        }
        if tool_definitions:
            kwargs["tools"] = tool_definitions
            kwargs["tool_choice"] = tool_choice

        if not stream_response:
            response = await create_chat_completion(
                llm_client,
                metric_stage=("agent.final@v1" if tool_choice == "none" else "agent.round@v1"),
                max_completion_tokens=max_completion_tokens,
                **kwargs,
            )
            message = response.choices[0].message
            tool_calls = tuple(
                ToolCallInfo(
                    id=tool_call.id or f"call_{index}",
                    type="function",
                    function=ToolCallFunction(
                        name=tool_call.function.name,
                        arguments=tool_call.function.arguments,
                    ),
                )
                for index, tool_call in enumerate(message.tool_calls or [])
            )
            return _AgentTurn(
                content=message.content or "",
                reasoning_content=getattr(message, "reasoning_content", "") or "",
                tool_calls=tool_calls,
                finish_reason=getattr(response.choices[0], "finish_reason", None),
            )

        content = ""
        reasoning_content = ""
        finish_reason: str | None = None
        tool_calls_accumulator: dict[int, dict[str, str]] = {}
        stream_text_immediately = tool_choice == "none"
        stream = stream_chat_completion(
            llm_client,
            metric_stage=("agent.final@v1" if tool_choice == "none" else "agent.round@v1"),
            max_completion_tokens=max_completion_tokens,
            **kwargs,
        )
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                chunk_finish_reason = getattr(choice, "finish_reason", None)
                if chunk_finish_reason is not None:
                    finish_reason = chunk_finish_reason
                delta = choice.delta
                if delta.content:
                    content += delta.content
                    if stream_text_immediately:
                        await emit(AgentEvent(type="text", content=delta.content))
                delta_reasoning = getattr(delta, "reasoning_content", "") or ""
                if delta_reasoning:
                    reasoning_content += delta_reasoning
                    await emit(AgentEvent(type="reasoning", content=delta_reasoning))
                for tool_call_delta in delta.tool_calls or []:
                    accumulator = tool_calls_accumulator.setdefault(
                        tool_call_delta.index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if tool_call_delta.id:
                        accumulator["id"] = tool_call_delta.id
                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            accumulator["name"] = tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            accumulator["arguments"] += tool_call_delta.function.arguments
        except LLMRetryableError:
            if not content.strip():
                raise
            finish_reason = "stream_error"

        return _AgentTurn(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tuple(tool_call_infos_from_stream(tool_calls_accumulator)),
            finish_reason=finish_reason,
        )

    async def _classify_tool_calls(
        self,
        state: _ExecutionState,
        tool_calls: list[ToolCallInfo],
        *,
        execution_context: AgentExecutionContext | None,
        tool_call_reserve: int,
    ) -> tuple[list[ToolResultInfo | None], list[tuple[int, ToolCallInfo]], list[tuple[int, ToolCallInfo]]]:
        """去重分类：成功结果重放 / 同轮重复占位 / 待执行；预算拒绝不计入已见。"""
        settings = (
            execution_context.settings
            if execution_context is not None
            else get_settings()
        )
        tool_results: list[ToolResultInfo | None] = [None] * len(tool_calls)
        unique_calls: list[tuple[int, ToolCallInfo]] = []
        for index, tool_call in enumerate(tool_calls):
            cache_key = tool_call_cache_key(tool_call)
            previous = state.succeeded_tool_results.get(cache_key)
            if previous is not None:
                # 相同工具+参数的成功结果直接重放：模型无需再调，上游零开销
                metrics.record_agentic_event("duplicate_tool_call")
                tool_results[index] = ToolResultInfo(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    content=(
                        "[重复调用已拦截] 本会话已用相同参数调用过该工具，以下为先前结果：\n"
                        + previous.content
                    ),
                    is_error=False,
                )
                continue
            if cache_key in state.seen_tool_call_keys:
                # 同轮并发重复：暂以错误占位
                metrics.record_agentic_event("duplicate_tool_call")
                tool_results[index] = ToolResultInfo(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    content=serialize_error(
                        "duplicate_tool_call",
                        "本 Agent 已调用过相同工具和参数，请基于已有结果继续分析",
                    ),
                    is_error=True,
                )
                continue
            state.seen_tool_call_keys.add(cache_key)
            unique_calls.append((index, tool_call))

        accepted_count = min(
            len(unique_calls),
            settings.chat_max_tool_calls_per_round,
        )
        if execution_context is not None:
            accepted_count = await execution_context.reserve_tool_calls(
                accepted_count,
                preserve=tool_call_reserve,
            )
        accepted_calls = unique_calls[:accepted_count]
        rejected_calls = unique_calls[accepted_count:]
        for _index, tool_call in rejected_calls:
            # 预算拒绝不算"已调用"：后续轮次允许再次发起
            state.seen_tool_call_keys.discard(tool_call_cache_key(tool_call))
        return tool_results, accepted_calls, rejected_calls

    async def run(
        self,
        profile: AgentProfile,
        message: str,
        history: list[AgentMessage] | None,
        llm_client: AsyncOpenAI,
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
        tool_dedupe: ToolCallDedupe | None = None,
    ) -> AgentExecutionResult:
        """使用统一执行引擎运行一个 AgentProfile。

        Param:
            message: 用户消息
            history: 历史消息列表，可选
            llm_client: 异步 OpenAI 客户端
            model: 模型名称
            event_queue: 可选事件队列，用于实时推送工具调用/结果增量
            tool_cache: 可选的跨 Agent 共享工具缓存，未提供时本 Agent 内部新建（仅本 Agent 内去重）
        Return:
            AgentExecutionResult，包含最终分析文本、调用过的工具和耗时
        """
        execution_context = execution_context or AgentExecutionContext.from_current(
            get_settings()
        )
        state = self._build_execution_state(
            profile,
            message,
            history,
            allowed_tool_names,
            tool_cache,
            execution_context,
            max_history_messages,
            tool_selection_prompt,
            tool_dedupe=tool_dedupe,
        )

        async def emit(delta: AgentEvent) -> None:
            """向事件队列推送一条增量（队列为空时静默忽略）。"""
            if event_queue is not None:
                await event_queue.put(delta)

        for round_num in range(profile.max_rounds):
            metrics.record_agentic_event("agent_round")
            tool_definitions = state.tool_definitions
            if (
                tool_definitions
                and execution_context.tool_calls_available(preserve=tool_call_reserve) <= 0
            ):
                tool_definitions = []
                if _TOOL_BUDGET_WARNING not in state.warnings:
                    state.warnings.append(_TOOL_BUDGET_WARNING)
            tool_choice = (
                "required"
                if round_num == 0 and tool_definitions and require_tool_first_round
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
                _, detail = _log_agent_llm_error(
                    f"Agent {profile.name} 模型调用",
                    exc,
                    "模型调用失败",
                )
                if is_llm_connection_error(exc):
                    # LLM 网关不可达是可重试的上游故障：快速失败并保留真实原因，
                    # 继续空转只会把根因伪装成"调研证据不足"误导排查与监控。
                    raise UpstreamUnavailableError(
                        "LLM 服务连接失败，请检查网络或代理配置后重试"
                    ) from exc
                state.errors.append(detail)
                if stream_response:
                    await emit(AgentEvent(type="error", error=detail))
                    return self._build_result(profile, state, "", "failed")
                break

            self._record_turn_completion(state, turn)

            tool_calls = list(turn.tool_calls)
            if not tool_calls and tool_definitions:
                tool_calls = extract_pseudo_tool_calls(
                    turn.content,
                    registry,
                    allowed_names=state.effective_tool_names,
                )
            if not tool_calls:
                if require_tool_evidence and not any(
                    result.has_evidence for result in state.tool_results
                ):
                    detail = "未获取有效工具证据，无法生成可靠结论"
                    state.errors.append(detail)
                    if stream_response:
                        await emit(AgentEvent(type="error", error=detail))
                    return self._build_result(profile, state, "", "failed", turn.reasoning_content)
                if not turn.content.strip():
                    state.errors.append(_EMPTY_OUTPUT_ERROR)
                    if stream_response:
                        await emit(AgentEvent(type="error", error=_EMPTY_OUTPUT_ERROR))
                    return self._build_result(
                        profile,
                        state,
                        "",
                        "failed",
                        turn.reasoning_content,
                    )
                if stream_response and turn.content and tool_choice != "none":
                    await emit(AgentEvent(type="text", content=turn.content))
                return self._build_result(
                    profile,
                    state,
                    turn.content,
                    "partial" if state.errors or state.warnings else "completed",
                    turn.reasoning_content,
                )

            await self._execute_tool_calls(
                profile,
                state,
                tool_calls,
                turn.content,
                emit,
                execution_context,
                tool_call_reserve,
            )

        if require_tool_evidence and not any(
            result.has_evidence for result in state.tool_results
        ):
            detail = "未获取有效工具证据，无法生成可靠结论"
            state.errors.append(detail)
            if stream_response:
                await emit(AgentEvent(type="error", error=detail))
            return self._build_result(profile, state, "", "failed")

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
        llm_client: AsyncOpenAI,
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
