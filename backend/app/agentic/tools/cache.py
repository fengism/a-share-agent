from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.runtime.metrics import metrics
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.process_cache import process_tool_cache
from app.agentic.tools.serialization import tool_call_cache_key, tool_call_cache_key_from_arguments

if TYPE_CHECKING:
    from app.agentic.runtime.context import AgentExecutionContext

# 失败不进入正常缓存（一次上游抖动会被放大成持续故障），但同一轮多 Agent
# 并发时，完全相同的瞬时失败会在几秒内被每个 Agent 重打一遍。只对可重试的
# 瞬时错误做很短时间的负缓存，认证/参数/编程错误永不缓存。
_NEGATIVE_CACHE_TTL_SECONDS = 5.0
_TRANSIENT_FAILURE_CODES = frozenset({"timeout", "upstream_unavailable", "rate_limited"})


@dataclass
class _SharedToolCacheEntry:
    future: asyncio.Future[ToolResultInfo]
    expires_at: float | None = None


class SharedToolCache:
    """Deduplicate identical Tool calls within one Agent execution context."""

    def __init__(self) -> None:
        self._cache: dict[str, _SharedToolCacheEntry] = {}
        self._negative_cache: dict[str, tuple[float, ToolResultInfo]] = {}

    def _negative_result(
        self,
        key: str,
        call: ToolCallInfo,
    ) -> ToolResultInfo | None:
        entry = self._negative_cache.get(key)
        if entry is None:
            return None
        expires_at, result = entry
        if expires_at <= time.monotonic():
            self._negative_cache.pop(key, None)
            return None
        metrics.record_agentic_event("tool_negative_cache_hit")
        return ToolResultInfo(
            tool_call_id=call.id,
            name=result.name,
            content=result.content,
            is_error=True,
        )

    def _store_negative(self, key: str, result: ToolResultInfo) -> None:
        if not _is_transient_failure(result):
            return
        self._negative_cache[key] = (
            time.monotonic() + _NEGATIVE_CACHE_TTL_SECONDS,
            result,
        )
        metrics.record_agentic_event("tool_negative_cache_store")

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

    def cache_key_for(
        self,
        call: ToolCallInfo,
        execution_context: "AgentExecutionContext | None" = None,
    ) -> str:
        """Public wrapper so callers can compute a scoped key once per call."""
        return self._cache_key(call, execution_context)

    def cache_key_for_arguments(
        self,
        name: str,
        arguments: Any,
        execution_context: "AgentExecutionContext | None" = None,
    ) -> str:
        """Compute a scoped key from already-parsed arguments."""
        policy = registry.get_tool_policy(name) or ToolPolicy()
        user_id = (
            execution_context.user_id
            if policy.scope == "user" and execution_context is not None
            else None
        )
        return tool_call_cache_key_from_arguments(name, arguments, user_id=user_id)

    def _get_entry(
        self,
        call: ToolCallInfo,
        execution_context: "AgentExecutionContext | None" = None,
        cache_key: str | None = None,
    ) -> _SharedToolCacheEntry | None:
        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        if policy.cache_ttl_seconds == 0:
            return None
        key = cache_key or self._cache_key(call, execution_context)
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
        *,
        cache_key: str | None = None,
    ) -> ToolResultInfo | None:
        """Return a completed, unexpired success without consuming execution budget."""
        if allowed_names is not None and call.function.name not in allowed_names:
            return None
        entry = self._get_entry(call, execution_context, cache_key)
        if entry is not None:
            if not entry.future.done() or entry.future.cancelled() or entry.future.exception() is not None:
                # 任务可能刚好在「已结束但还没摘掉条目」的窗口里被看到。异常必须先判断
                # 再取：直接 future.result() 会把异常抛穿 agent，而这里不在任何 try 内。
                # 未完成的条目交给 execute_shared 去 await，不去读可能更旧的进程缓存。
                return None
            result = entry.future.result()
            if result.is_error:
                return None
            metrics.record_agentic_event("tool_cache_hit")
            return ToolResultInfo(
                tool_call_id=call.id, name=result.name,
                content=result.content, is_error=result.is_error,
            )
        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        if self._process_cache_enabled(policy, execution_context):
            key = cache_key or self._cache_key(call, execution_context)
            return process_tool_cache.get(key, call.id)
        return None

    async def execute(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
        execution_context: AgentExecutionContext | None = None,
        *,
        cache_key: str | None = None,
        arguments: Any | None = None,
    ) -> ToolResultInfo:
        result, _ = await self.execute_shared(
            call,
            allowed_names=allowed_names,
            execution_context=execution_context,
            cache_key=cache_key,
            arguments=arguments,
        )
        return result

    async def execute_shared(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
        execution_context: AgentExecutionContext | None = None,
        *,
        cache_key: str | None = None,
        arguments: Any | None = None,
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
                    arguments=arguments,
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
                    arguments=arguments,
                ),
                False,
            )

        # scope="user" 的工具结果依赖用户私有配置，必须按 user 分区。
        key = cache_key or self._cache_key(call, execution_context)
        existing = self._get_entry(call, execution_context, key)
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

        # 跨请求缓存：policy 已经声明了可复用时长（cache_ttl_seconds/freshness），
        # 但此前只在单个执行上下文内生效。
        process_cache_store = self._process_cache_enabled(policy, execution_context)
        if process_cache_store:
            cross_request = process_tool_cache.get(key, call.id)
            if cross_request is not None:
                return cross_request, True

        negative = self._negative_result(key, call)
        if negative is not None:
            return negative, True

        metrics.record_agentic_event("tool_cache_miss")
        task: asyncio.Task[ToolResultInfo] = asyncio.create_task(
            self._run_shared(
                key, policy, call, allowed_names, execution_context, arguments, process_cache_store,
            ),
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

    @staticmethod
    def _process_cache_enabled(
        policy: ToolPolicy,
        execution_context: "AgentExecutionContext | None",
    ) -> bool:
        """Whether this call may read/write the process-wide cache.

        The toggle lives on the request settings so no extra settings lookup is
        needed per tool call. Standalone runs (no execution context) only use the
        per-request cache, which keeps unit tests and extracted usage isolated.
        """
        if execution_context is None:
            return False
        if not bool(getattr(execution_context.settings, "chat_tool_process_cache_enabled", True)):
            return False
        return process_tool_cache.eligible(policy)

    async def _run_shared(
        self,
        key: str,
        policy: ToolPolicy,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None,
        execution_context: "AgentExecutionContext | None",
        arguments: Any | None = None,
        process_cache_store: bool = False,
    ) -> ToolResultInfo:
        """执行共享工作并维护缓存条目；所有等待者拿到同一份结果。"""
        try:
            result = await registry.execute_tool(
                call,
                allowed_names=allowed_names,
                execution_context=execution_context,
                arguments=arguments,
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
            self._store_negative(key, result)
            metrics.record_agentic_event("tool_failure")
            return result
        self._negative_cache.pop(key, None)
        entry = self._cache.get(key)
        if entry is not None:
            entry.expires_at = time.monotonic() + policy.cache_ttl_seconds
        if process_cache_store:
            process_tool_cache.put(key, result, policy.cache_ttl_seconds)
        metrics.record_agentic_event("tool_success")
        return result


def _is_transient_failure(result: ToolResultInfo) -> bool:
    if not result.is_error:
        return False
    try:
        payload = json.loads(result.content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return False
    return error.get("code") in _TRANSIENT_FAILURE_CODES and error.get("retryable") is True


def _retrieve_task_exception(task: asyncio.Task[ToolResultInfo]) -> None:
    """取出任务异常，避免无人 await 时刷「exception was never retrieved」。

    提前取出不影响后续等待者：``await`` 同一个 task 仍会照常抛出该异常。
    """
    if not task.cancelled():
        task.exception()


__all__ = ["SharedToolCache"]
