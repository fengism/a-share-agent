from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
from app.agentic.agents.executor import AgentExecutor, agent_executor
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.contracts import (
    MAX_EVIDENCE_ARGUMENT_LENGTH,
    AgentEvidence,
    AgentResearchSpec,
    AgentRoundResult,
)
from app.agentic.events import AgentEvent
from app.agentic.research import AgentEventCallback, build_research_system_prompt
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.runtime.research_policy import ResearchSearchPolicy
from app.agentic.tools.serialization import has_meaningful_tool_content
from app.configuration import get_effective_settings
from app.infrastructure.llm.adapters import LLMInvalidResponseError
from app.infrastructure.llm.policy import generation_scope
from app.infrastructure.llm.runtime import borrow_async_openai_chat_runtime

logger = logging.getLogger(__name__)
_INCOMPLETE_SUMMARY_REASONS = {
    "length": "模型输出达到长度上限",
    "stream_error": "模型流式响应中断或缺少结束帧",
    "empty_response": "模型未返回有效摘要",
}
_FATAL_REASONS = {
    "content_filter": "模型内容过滤终止输出",
    "invalid_response": "模型响应格式不兼容",
    "generation_error": "模型请求失败",
    "bad_request": "模型请求参数不被上游接受",
    "authentication_error": "模型鉴权失败",
    "permission_error": "模型访问权限不足",
    "rate_limited": "模型服务限流",
    "unexpected_finish": "模型返回未知结束状态",
    "tool_calls": "最终摘要错误地返回工具调用结束状态",
}


def _collect_round_evidence(events: list[AgentEvent]) -> tuple[AgentEvidence, ...]:
    calls: dict[str, tuple[str, str]] = {}
    evidence: list[AgentEvidence] = []
    for delta in events:
        if delta.type == "tool_call" and delta.tool_call is not None:
            calls[delta.tool_call.id] = (
                delta.tool_call.function.name,
                delta.tool_call.function.arguments,
            )
        elif (
            delta.type == "tool_result"
            and delta.tool_result is not None
            and (
                delta.tool_result.is_error
                or has_meaningful_tool_content(delta.tool_result.content)
            )
        ):
            tool_name, arguments = calls.get(
                delta.tool_result.tool_call_id,
                (delta.tool_result.name, "{}"),
            )
            evidence.append(AgentEvidence(
                tool_call_id=delta.tool_result.tool_call_id,
                tool_name=tool_name,
                arguments=arguments[:MAX_EVIDENCE_ARGUMENT_LENGTH],
                content=delta.tool_result.content,
                is_error=delta.tool_result.is_error,
            ))
    return tuple(evidence)


@dataclass(frozen=True)
class _ResearchExecutionCompleted:
    result: AgentExecutionResult


@dataclass(frozen=True)
class _ResearchExecutionFailed:
    exception: BaseException


@dataclass
class _AgentExecutorResearchSession:
    profile: AgentProfile
    executor: AgentExecutor
    client: Any
    model: str
    temperature: float
    execution_context: AgentExecutionContext
    allow_incomplete_summary: bool = False

    async def run(
        self,
        message: str,
        allowed_tool_names: tuple[str, ...],
        event_callback: AgentEventCallback | None = None,
        tool_call_reserve: int = 0,
    ) -> AgentRoundResult:
        used_before = self.execution_context.tool_calls_used
        if self.execution_context.tool_calls_available(preserve=tool_call_reserve) <= 0:
            reason = ("本轮无可用工具额度，未发起模型/工具调用；"
                      f"总剩余{self.execution_context.tool_calls_remaining}次，预留{tool_call_reserve}次。")
            if event_callback is not None:
                await event_callback(AgentEvent(type="status", content=reason))
            return AgentRoundResult(summary=reason, tool_calls_remaining=self.execution_context.tool_calls_remaining)
        event_queue: asyncio.Queue[
            AgentEvent | _ResearchExecutionCompleted | _ResearchExecutionFailed
        ] = asyncio.Queue()
        events: list[AgentEvent] = []
        message += (
            f"\n运行时工具预算：总上限{self.execution_context.settings.chat_max_tool_calls_total}次；"
            f"当前剩余{self.execution_context.tool_calls_remaining}次；每批最多{self.execution_context.settings.chat_max_tool_calls_per_round}次；"
            f"剩余正文专用额度{self.execution_context.reserved_calls_remaining}次。"
            "先读取已发现的正文再扩展搜索；不得将预算拒绝写成未披露。"
        )

        async def execute() -> None:
            try:
                result = await self.executor.run(
                    self.profile,
                    message,
                    None,
                    self.client,
                    self.model,
                    event_queue=event_queue,
                    allowed_tool_names=allowed_tool_names,
                    temperature=self.temperature,
                    require_tool_evidence=True,
                    stream_response=True,
                    execution_context=self.execution_context,
                    tool_call_reserve=tool_call_reserve,
                )
                await event_queue.put(_ResearchExecutionCompleted(result))
            except BaseException as error:
                await event_queue.put(_ResearchExecutionFailed(error))

        execution_task = asyncio.create_task(execute())
        try:
            while True:
                event = await event_queue.get()
                if isinstance(event, _ResearchExecutionFailed):
                    raise event.exception
                if isinstance(event, _ResearchExecutionCompleted):
                    result = event.result
                    break
                events.append(event)
                # Defer terminal errors until we know whether tool evidence is recoverable.
                if event_callback is not None and event.type != "error":
                    await event_callback(event)
        finally:
            if not execution_task.done():
                execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)

        evidence = _collect_round_evidence(events)
        stop_reason = ""
        if result.status != "completed" and not result.retryable:
            # Retryability controls replay, not whether already acquired facts may be retained.
            reason = result.termination_reason
            safe_reason = reason if reason in {*_INCOMPLETE_SUMMARY_REASONS, *_FATAL_REASONS} else "unknown"
            usable_count = sum(not item.is_error and has_meaningful_tool_content(item.content) for item in evidence)
            logger.warning(
                "Agent调研非完整结束: agent=%s status=%s reason=%s tool_requests=%d evidence=%d",
                self.profile.name, result.status, safe_reason, len(result.tools_called), usable_count,
            )
            if self.allow_incomplete_summary and reason in _INCOMPLETE_SUMMARY_REASONS and usable_count:
                stop_reason = f"{_INCOMPLETE_SUMMARY_REASONS[reason]}；已保留{usable_count}条有效工具结果，停止继续调研，报告需按证据不足降级。"
                if event_callback is not None:
                    await event_callback(AgentEvent(type="status", content=stop_reason))
            else:
                description = _INCOMPLETE_SUMMARY_REASONS.get(reason) or _FATAL_REASONS.get(reason) or "模型执行未完成，结束原因未提供"
                detail = f"Agent 调研停止：{description}（reason={safe_reason}，有效工具结果{usable_count}条）"
                if event_callback is not None:
                    await event_callback(AgentEvent(type="error", error=detail))
                raise LLMInvalidResponseError(detail)

        if event_callback is not None:
            await event_callback(AgentEvent(type="status", content=(
                f"本轮模型请求工具{len(result.tools_called)}次，"
                f"新增执行{self.execution_context.tool_calls_used - used_before}次，"
                f"总剩余{self.execution_context.tool_calls_remaining}次，其中正文预留{self.execution_context.reserved_calls_remaining}次。"
                "新增执行不含缓存复用；工具请求可能被预算拒绝。"
            )))
            if result.status == "failed" and not stop_reason:
                for event in events:
                    if event.type == "error":
                        await event_callback(event)
            if self.execution_context.search_policy is not None:
                policy = self.execution_context.search_policy
                await event_callback(AgentEvent(type="status", content=(
                    f"搜索规划：已执行{policy.used}/{policy.total_limit}次；"
                    f"未读候选来源{len(policy.pending_urls)}个；连续搜索上限{policy.burst_limit}次。"
                    "搜索结果不等于正文，读取失败不会标为核实。"
                )))
            for warning in result.warnings:
                await event_callback(AgentEvent(type="status", content=warning))
        return AgentRoundResult(
            # Never promote a truncated/empty summary or a tool error body into facts.
            summary="" if stop_reason else result.analysis.strip(),
            evidence=evidence,
            stop_reason=stop_reason,
            tool_calls_remaining=self.execution_context.tool_calls_remaining,
        )


class AgentExecutorResearchRuntime:
    @asynccontextmanager
    async def open_session(
        self,
        spec: AgentResearchSpec,
        settings: Any = None,
    ) -> AsyncIterator[_AgentExecutorResearchSession]:
        register_all_capabilities()
        effective_settings = settings or get_effective_settings()
        profile = AgentProfile(
            name=spec.name,
            display_name=spec.display_name,
            description=spec.display_name,
            system_prompt=build_research_system_prompt(spec),
            tool_names=spec.tool_names,
            max_rounds=spec.max_tool_turns or spec.max_rounds,
        )
        temperature = effective_settings.llm_temperature
        execution_context = AgentExecutionContext.from_current(
            effective_settings, total_timeout_seconds=effective_settings.agent_research_timeout_seconds,
        )
        execution_context.reserved_tool_names = spec.reserved_tool_names
        execution_context.reserved_tool_calls = spec.reserved_tool_calls
        if spec.search_tool_names:
            execution_context.search_policy = ResearchSearchPolicy(
                spec.search_tool_names, spec.search_total_limit, spec.search_burst_limit, spec.reserved_tool_names,
            )
        async with generation_scope(
            effective_settings, timeout_seconds=effective_settings.agent_research_timeout_seconds, label="Agent 调研",
        ), borrow_async_openai_chat_runtime(effective_settings) as runtime:
            yield _AgentExecutorResearchSession(
                profile=profile,
                executor=agent_executor,
                client=runtime.client,
                model=runtime.model,
                temperature=temperature,
                execution_context=execution_context,
                allow_incomplete_summary=spec.allow_incomplete_summary,
            )
