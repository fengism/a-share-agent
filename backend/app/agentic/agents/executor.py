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
from app.agentic.protocol import AgentMessage, ToolCallFunction, ToolCallInfo, ToolResultInfo
from app.agentic.runtime.llm import create_chat_completion, stream_chat_completion
from app.agentic.tools.calls import (
    build_assistant_tool_message,
    extract_pseudo_tool_calls,
    tool_call_infos_from_stream,
)
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.serialization import tool_call_cache_key
from app.core.errors import log_internal_error

logger = logging.getLogger(__name__)


@dataclass
class _SharedToolCacheEntry:
    future: asyncio.Future[ToolResultInfo]
    expires_at: float | None = None


class SharedToolCache:
    """跨子 Agent 共享的工具结果缓存：name+arguments 相同的调用只执行一次。

    用 in-flight future 缓存：先到的调用占位并执行，后到的（含并发）直接 await 同一结果。
    单线程事件循环下「查缓存→建 future」之间无 await，故 check-and-set 原子，能真正去重并发调用。
    """

    def __init__(self) -> None:
        self._cache: dict[str, _SharedToolCacheEntry] = {}

    @staticmethod
    def _key(call: ToolCallInfo) -> str:
        return tool_call_cache_key(call)

    async def execute(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
    ) -> ToolResultInfo:
        """执行工具调用并缓存结果，命中时用本次 tool_call_id 重新封装返回。

        Param:
            call: 工具调用信息
        Return:
            ToolResultInfo，tool_call_id 始终对应本次调用
        """
        if allowed_names is not None and call.function.name not in allowed_names:
            return await registry.execute_tool(call, allowed_names=allowed_names)

        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        if policy.cache_ttl_seconds == 0:
            if allowed_names is None:
                return await registry.execute_tool(call)
            return await registry.execute_tool(call, allowed_names=allowed_names)

        key = self._key(call)
        existing = self._cache.get(key)
        if existing is not None:
            if existing.expires_at is None or existing.expires_at > time.monotonic():
                cached = await existing.future
                return ToolResultInfo(
                    tool_call_id=call.id, name=cached.name,
                    content=cached.content, is_error=cached.is_error,
                )
            self._cache.pop(key, None)

        loop = asyncio.get_event_loop()
        fut: asyncio.Future[ToolResultInfo] = loop.create_future()
        entry = _SharedToolCacheEntry(future=fut)
        self._cache[key] = entry
        try:
            if allowed_names is None:
                result = await registry.execute_tool(call)
            else:
                result = await registry.execute_tool(call, allowed_names=allowed_names)
        except BaseException:
            # registry.execute_tool 正常不抛异常，但兜底：失败不缓存，避免毒化
            self._cache.pop(key, None)
            if not fut.done():
                fut.cancel()
            raise
        if result.is_error:
            self._cache.pop(key, None)
        else:
            entry.expires_at = time.monotonic() + policy.cache_ttl_seconds
        fut.set_result(result)
        return result


@dataclass(frozen=True, slots=True)
class _AgentTurn:
    content: str
    reasoning_content: str
    tool_calls: tuple[ToolCallInfo, ...]


@dataclass(frozen=True, slots=True)
class _ExecutionCompleted:
    result: AgentExecutionResult


@dataclass(frozen=True, slots=True)
class _ExecutionFailed:
    error: BaseException


@dataclass(slots=True)
class _ExecutionState:
    started_at: float
    messages: list[dict]
    effective_tool_names: list[str]
    tool_definitions: list[dict]
    tool_cache: SharedToolCache
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[ToolExecutionSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AgentExecutor:
    @staticmethod
    def _build_execution_state(
        profile: AgentProfile,
        message: str,
        history: list[AgentMessage] | None,
        allowed_tool_names: Collection[str] | None,
        tool_cache: SharedToolCache | None,
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
            tool_cache=tool_cache or SharedToolCache(),
        )

    @staticmethod
    def _build_result(
        profile: AgentProfile,
        state: _ExecutionState,
        analysis: str,
        status: Literal["completed", "partial", "failed"],
        reasoning_content: str = "",
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_name=profile.name,
            display_name=profile.display_name,
            analysis=analysis,
            status=status,
            tools_called=state.tools_called,
            tool_results=state.tool_results,
            errors=state.errors,
            duration_ms=int((time.monotonic() - state.started_at) * 1000),
            reasoning_content=reasoning_content,
        )

    async def _execute_tool_calls(
        self,
        profile: AgentProfile,
        state: _ExecutionState,
        tool_calls: list[ToolCallInfo],
        assistant_content: str,
        emit: Callable[[AgentEvent], Awaitable[None]],
    ) -> None:
        state.messages.append(build_assistant_tool_message(tool_calls, assistant_content))
        for tool_call in tool_calls:
            state.tools_called.append(tool_call.function.name)
            await emit(AgentEvent(type="tool_call", tool_call=tool_call))

        tool_results = await asyncio.gather(
            *(
                state.tool_cache.execute(
                    tool_call,
                    allowed_names=state.effective_tool_names,
                )
                for tool_call in tool_calls
            )
        )
        for tool_call, result in zip(tool_calls, tool_results):
            await emit(AgentEvent(type="tool_result", tool_result=result))
            state.tool_results.append(
                ToolExecutionSummary(
                    name=tool_call.function.name,
                    is_error=result.is_error,
                )
            )
            state.messages.append({
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": result.content,
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
            )
            analysis = turn.content
            reasoning_content = turn.reasoning_content
        except Exception as exc:
            generation_failed = True
            _, analysis = log_internal_error(
                logger,
                f"Agent {profile.name} 最终分析",
                exc,
                "最终分析生成失败",
            )
            state.errors.append(analysis)
            if stream_response:
                await emit(AgentEvent(type="error", error=analysis))

        status: Literal["completed", "partial", "failed"]
        if generation_failed or not analysis.strip():
            status = "failed"
        elif state.errors:
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
            response = await create_chat_completion(llm_client, **kwargs)
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
            )

        content = ""
        reasoning_content = ""
        tool_calls_accumulator: dict[int, dict[str, str]] = {}
        stream_text_immediately = tool_choice == "none"
        stream = stream_chat_completion(llm_client, **kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
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

        return _AgentTurn(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tuple(tool_call_infos_from_stream(tool_calls_accumulator)),
        )

    async def run(
        self,
        profile: AgentProfile,
        message: str,
        history: list[AgentMessage] | None,
        llm_client: AsyncOpenAI,
        model: str,
        event_queue: asyncio.Queue | None = None,
        tool_cache: "SharedToolCache | None" = None,
        allowed_tool_names: Collection[str] | None = None,
        temperature: float = 0.1,
        tool_selection_prompt: str = "",
        max_history_messages: int = 10,
        require_tool_first_round: bool = True,
        stream_response: bool = False,
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
        state = self._build_execution_state(
            profile,
            message,
            history,
            allowed_tool_names,
            tool_cache,
            max_history_messages,
            tool_selection_prompt,
        )

        async def emit(delta: AgentEvent) -> None:
            """向事件队列推送一条增量（队列为空时静默忽略）。"""
            if event_queue is not None:
                await event_queue.put(delta)

        for round_num in range(profile.max_rounds):
            tool_choice = (
                "required"
                if round_num == 0 and state.tool_definitions and require_tool_first_round
                else "auto"
                if state.tool_definitions
                else "none"
            )
            try:
                turn = await self._complete_turn(
                    llm_client,
                    model=model,
                    messages=state.messages,
                    tool_definitions=state.tool_definitions,
                    tool_choice=tool_choice,
                    temperature=temperature,
                    stream_response=stream_response,
                    emit=emit,
                )
            except Exception as exc:
                _, detail = log_internal_error(
                    logger,
                    f"Agent {profile.name} 模型调用",
                    exc,
                    "模型调用失败",
                )
                state.errors.append(detail)
                if stream_response:
                    await emit(AgentEvent(type="error", error=detail))
                    return self._build_result(profile, state, "", "failed")
                break

            tool_calls = list(turn.tool_calls)
            if not tool_calls and state.tool_definitions:
                tool_calls = extract_pseudo_tool_calls(
                    turn.content,
                    registry,
                    allowed_names=state.effective_tool_names,
                )
            if not tool_calls:
                if stream_response and turn.content and tool_choice != "none":
                    await emit(AgentEvent(type="text", content=turn.content))
                return self._build_result(
                    profile,
                    state,
                    turn.content,
                    "partial" if state.errors else "completed",
                    turn.reasoning_content,
                )

            await self._execute_tool_calls(
                profile,
                state,
                tool_calls,
                turn.content,
                emit,
            )

        return await self._complete_final_result(
            profile,
            state,
            llm_client,
            model,
            temperature,
            stream_response,
            emit,
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
                    raise event.error
                if isinstance(event, _ExecutionCompleted):
                    if event.result.status != "failed":
                        yield AgentEvent(
                            type="done",
                            reasoning_content=event.result.reasoning_content or None,
                        )
                    break
                yield event
        finally:
            if not execution_task.done():
                execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)


agent_executor = AgentExecutor()
