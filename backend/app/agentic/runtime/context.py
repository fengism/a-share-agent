from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.agentic.runtime.research_policy import ResearchSearchPolicy
from app.agentic.tools.cache import SharedToolCache
from app.configuration.schema import Settings
from app.core.request_context import get_current_request_id, get_current_user_id


@dataclass(slots=True)
class AgentExecutionContext:
    settings: Settings
    user_id: int | None = None
    request_id: str | None = None
    deadline: float | None = None
    tool_cache: SharedToolCache = field(default_factory=SharedToolCache)
    reserved_tool_names: tuple[str, ...] = ()
    reserved_tool_calls: int = 0
    search_policy: ResearchSearchPolicy | None = None
    _reserved_calls_used: int = field(default=0, init=False, repr=False)
    _tool_calls_used: int = field(default=0, init=False, repr=False)
    _tool_budget_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    @classmethod
    def from_current(
        cls,
        settings: Settings,
        *,
        total_timeout_seconds: float | None = None,
    ) -> AgentExecutionContext:
        deadline = None
        if total_timeout_seconds is not None:
            deadline = time.monotonic() + max(1.0, float(total_timeout_seconds))
        return cls(
            settings=settings,
            user_id=get_current_user_id(),
            request_id=get_current_request_id(),
            deadline=deadline,
        )

    def deadline_exceeded(self) -> bool:
        """整体 deadline 是否已耗尽。"""
        return self.deadline is not None and time.monotonic() >= self.deadline

    def bounded_timeout(self, requested_seconds: float) -> float:
        timeout_seconds = max(0.001, float(requested_seconds))
        if self.deadline is None:
            return timeout_seconds
        return max(0.001, min(timeout_seconds, self.deadline - time.monotonic()))

    def tool_calls_available(self, *, preserve: int = 0, tool_name: str | None = None) -> int:
        preserved_calls = min(
            max(0, int(preserve)),
            max(0, self.settings.chat_max_tool_calls_total // 2),
        )
        if tool_name is not None and tool_name not in self.reserved_tool_names:
            preserved_calls = max(preserved_calls, self.reserved_calls_remaining)
        available = max(0, self.tool_calls_remaining - preserved_calls)
        if self.search_policy is not None and tool_name in self.search_policy.tool_names:
            available = min(available, self.search_policy.available)
        return available

    async def reserve_tool_calls(self, requested: int, *, preserve: int = 0, tool_name: str | None = None) -> int:
        requested_calls = max(0, int(requested))
        async with self._tool_budget_lock:
            accepted = min(
                requested_calls,
                self.tool_calls_available(preserve=preserve, tool_name=tool_name),
            )
            self._tool_calls_used += accepted
            if self.search_policy is not None and tool_name in self.search_policy.tool_names:
                self.search_policy.consume(accepted)
            if tool_name in self.reserved_tool_names:
                self._reserved_calls_used += accepted
            return accepted

    @property
    def reserved_calls_remaining(self) -> int:
        return max(0, min(self.reserved_tool_calls, self.settings.chat_max_tool_calls_total // 2) - self._reserved_calls_used)

    @property
    def tool_calls_used(self) -> int:
        return self._tool_calls_used

    @property
    def tool_calls_remaining(self) -> int:
        return max(0, self.settings.chat_max_tool_calls_total - self._tool_calls_used)


__all__ = ["AgentExecutionContext"]
