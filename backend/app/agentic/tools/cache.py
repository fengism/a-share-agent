from __future__ import annotations

import asyncio
import time
from collections.abc import Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.serialization import tool_call_cache_key
from app.core.metrics import metrics

if TYPE_CHECKING:
    from app.agentic.runtime.context import AgentExecutionContext


@dataclass
class _SharedToolCacheEntry:
    future: asyncio.Future[ToolResultInfo]
    expires_at: float | None = None


class SharedToolCache:
    """Deduplicate identical Tool calls within one Agent execution context."""

    def __init__(self) -> None:
        self._cache: dict[str, _SharedToolCacheEntry] = {}

    @staticmethod
    def _cache_key(
        call: ToolCallInfo,
        execution_context: "AgentExecutionContext | None" = None,
    ) -> str:
        """构造缓存 key；scope="user" 的工具按 user 分区。

        此前 key 里没有用户维度，只是因为本类恰好是 per-request 实例（挂在
        AgentExecutionContext 的 default_factory 字段上）。一旦缓存被提升到模块级、
        或被后台 workflow 复用，两个用户的私有配置就会互相串用，而没有任何类型或测试能挡住。
        """
        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        user_id = (
            execution_context.user_id
            if policy.scope == "user" and execution_context is not None
            else None
        )
        return tool_call_cache_key(call, user_id=user_id)

    def _get_entry(
        self,
        call: ToolCallInfo,
        execution_context: "AgentExecutionContext | None" = None,
    ) -> _SharedToolCacheEntry | None:
        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        if policy.cache_ttl_seconds == 0:
            return None
        key = self._cache_key(call, execution_context)
        entry = self._cache.get(key)
        if entry is not None and (
            entry.future.cancelled()
            or (entry.expires_at is not None and entry.expires_at <= time.monotonic())
        ):
            self._cache.pop(key, None)
            metrics.record_agentic_event("tool_cache_expired")
            return None
        return entry

    def get_cached_result(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
        execution_context: "AgentExecutionContext | None" = None,
    ) -> ToolResultInfo | None:
        """Return a completed, unexpired success without consuming execution budget."""
        if allowed_names is not None and call.function.name not in allowed_names:
            return None
        entry = self._get_entry(call, execution_context)
        if entry is None or not entry.future.done():
            return None
        if entry.future.cancelled() or entry.future.exception() is not None:
            # 任务可能刚好在「已结束但还没摘掉条目」的窗口里被看到。异常必须先判断
            # 再取：直接 future.result() 会把异常抛穿 agent，而这里不在任何 try 内。
            return None
        result = entry.future.result()
        if result.is_error:
            return None
        metrics.record_agentic_event("tool_cache_hit")
        return ToolResultInfo(
            tool_call_id=call.id, name=result.name,
            content=result.content, is_error=result.is_error,
        )

    async def execute(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
        execution_context: AgentExecutionContext | None = None,
    ) -> ToolResultInfo:
        result, _ = await self.execute_shared(
            call, allowed_names=allowed_names, execution_context=execution_context
        )
        return result

    async def execute_shared(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
        execution_context: AgentExecutionContext | None = None,
    ) -> tuple[ToolResultInfo, bool]:
        """返回 ``(结果, 是否由已有条目提供)``。

        第二个值为 True 表示本次没有真实执行工具：命中已完成的缓存，或与另一个
        并发调用合并成同一次执行。调用方据此退回工具预算——预留在「决定执行」时就
        发生了，而「是否真的需要执行」要等进缓存那一刻才知道。
        """
        if allowed_names is not None and call.function.name not in allowed_names:
            return (
                await registry.execute_tool(
                    call,
                    allowed_names=allowed_names,
                    execution_context=execution_context,
                ),
                False,
            )

        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        if policy.cache_ttl_seconds == 0:
            return (
                await registry.execute_tool(
                    call,
                    allowed_names=allowed_names,
                    execution_context=execution_context,
                ),
                False,
            )

        # scope="user" 的工具结果依赖用户私有配置，必须按 user 分区。
        key = self._cache_key(call, execution_context)
        existing = self._get_entry(call, execution_context)
        if existing is not None:
            metrics.record_agentic_event("tool_cache_hit")
            cached = await asyncio.shield(existing.future)
            return (
                ToolResultInfo(
                    tool_call_id=call.id,
                    name=cached.name,
                    content=cached.content,
                    is_error=cached.is_error,
                ),
                True,
            )

        metrics.record_agentic_event("tool_cache_miss")
        task: asyncio.Task[ToolResultInfo] = asyncio.create_task(
            self._run_shared(key, policy, call, allowed_names, execution_context),
            name=f"tool:{call.function.name}",
        )
        entry = _SharedToolCacheEntry(future=task)
        self._cache[key] = entry
        # 工作跑在独立 task 里，与发起者的生命周期解耦：发起者被取消（客户端断连、
        # 外层 asyncio.timeout、plan 层批量 cancel）只会让 shield 把 CancelledError
        # 抛给发起者本人，共享工作与其它等待者不受影响。此前工作内联在发起者任务里，
        # 一个 future.cancel() 就能把等待者一起带走。
        task.add_done_callback(_retrieve_task_exception)
        return await asyncio.shield(task), False

    async def _run_shared(
        self,
        key: str,
        policy: ToolPolicy,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None,
        execution_context: "AgentExecutionContext | None",
    ) -> ToolResultInfo:
        """执行共享工作并维护缓存条目；所有等待者拿到同一份结果。"""
        try:
            result = await registry.execute_tool(
                call,
                allowed_names=allowed_names,
                execution_context=execution_context,
            )
        except asyncio.CancelledError:
            self._cache.pop(key, None)
            raise
        except Exception:
            # 失败结果不缓存：一次上游抖动被缓存下来会放大成持续故障。
            self._cache.pop(key, None)
            metrics.record_agentic_event("tool_failure")
            raise
        if result.is_error:
            self._cache.pop(key, None)
            metrics.record_agentic_event("tool_failure")
            return result
        entry = self._cache.get(key)
        if entry is not None:
            entry.expires_at = time.monotonic() + policy.cache_ttl_seconds
        metrics.record_agentic_event("tool_success")
        return result


def _retrieve_task_exception(task: asyncio.Task[ToolResultInfo]) -> None:
    """取出任务异常，避免无人 await 时刷「exception was never retrieved」。

    提前取出不影响后续等待者：``await`` 同一个 task 仍会照常抛出该异常。
    """
    if not task.cancelled():
        task.exception()


__all__ = ["SharedToolCache"]
