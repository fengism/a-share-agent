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
        if allowed_names is not None and call.function.name not in allowed_names:
            return await registry.execute_tool(
                call,
                allowed_names=allowed_names,
                execution_context=execution_context,
            )

        policy = registry.get_tool_policy(call.function.name) or ToolPolicy()
        if policy.cache_ttl_seconds == 0:
            return await registry.execute_tool(
                call,
                allowed_names=allowed_names,
                execution_context=execution_context,
            )

        # scope="user" 的工具结果依赖用户私有配置，必须按 user 分区。
        key = self._cache_key(call, execution_context)
        existing = self._get_entry(call, execution_context)
        if existing is not None:
            metrics.record_agentic_event("tool_cache_hit")
            cached = await asyncio.shield(existing.future)
            return ToolResultInfo(
                tool_call_id=call.id,
                name=cached.name,
                content=cached.content,
                is_error=cached.is_error,
            )

        metrics.record_agentic_event("tool_cache_miss")
        future: asyncio.Future[ToolResultInfo] = asyncio.get_running_loop().create_future()
        entry = _SharedToolCacheEntry(future=future)
        self._cache[key] = entry
        try:
            result = await registry.execute_tool(
                call,
                allowed_names=allowed_names,
                execution_context=execution_context,
            )
        except BaseException:
            self._cache.pop(key, None)
            if not future.done():
                future.cancel()
            raise

        if result.is_error:
            self._cache.pop(key, None)
            metrics.record_agentic_event("tool_failure")
        else:
            entry.expires_at = time.monotonic() + policy.cache_ttl_seconds
            metrics.record_agentic_event("tool_success")
        future.set_result(result)
        return result


__all__ = ["SharedToolCache"]
