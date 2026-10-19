from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.agentic.runtime.research_policy import ResearchSearchPolicy
from app.agentic.runtime.settings import AgentSettings
from app.agentic.tools.cache import SharedToolCache

_request_context_provider: Callable[[], tuple[int | None, str | None]] | None = None


def configure_request_context_provider(
    provider: Callable[[], tuple[int | None, str | None]],
) -> None:
    """Install the host's request-scoped user/request-id lookup."""
    global _request_context_provider
    _request_context_provider = provider


def _current_request_ids() -> tuple[int | None, str | None]:
    if _request_context_provider is None:
        return None, None
    return _request_context_provider()


@dataclass(frozen=True, slots=True, eq=False)
class ToolCallReservation:
    """Context-owned single-call receipt. Identity, not caller-supplied fields, authorizes a refund."""

    reservation_id: int
    tool_name: str | None
    search: bool
    reserved: bool
    search_epoch: int = 0
    budget_kind: Literal["tool", "skill"] = "tool"


@dataclass(slots=True)
class AgentExecutionContext:
    settings: AgentSettings
    user_id: int | None = None
    request_id: str | None = None
    deadline: float | None = None
    tool_cache: SharedToolCache = field(default_factory=SharedToolCache)
    reserved_tool_names: tuple[str, ...] = ()
    reserved_tool_calls: int = 0
    # None means standalone/unrestricted; an empty tuple means no Skill is enabled.
    allowed_skill_names: tuple[str, ...] | None = None
    # Tools a loaded Skill may add dynamically; None means unrestricted.
    enabled_tool_names: tuple[str, ...] | None = None
    active_skill_names: tuple[str, ...] = ()
    search_policy: ResearchSearchPolicy | None = None
    _reserved_calls_used: int = field(default=0, init=False, repr=False)
    _tool_calls_used: int = field(default=0, init=False, repr=False)
    _skill_loads_used: int = field(default=0, init=False, repr=False)
    _reservation_sequence: int = field(default=0, init=False, repr=False)
    _active_tool_reservations: dict[int, ToolCallReservation] = field(default_factory=dict, init=False, repr=False)
    _tool_budget_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    @classmethod
    def from_current(
        cls,
        settings: AgentSettings,
        *,
        total_timeout_seconds: float | None = None,
        user_id: int | None = None,
        request_id: str | None = None,
    ) -> AgentExecutionContext:
        deadline = None
        if total_timeout_seconds is not None:
            deadline = time.monotonic() + max(1.0, float(total_timeout_seconds))
        if user_id is None and request_id is None:
            user_id, request_id = _current_request_ids()
        return cls(
            settings=settings,
            user_id=user_id,
            request_id=request_id,
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

    def _reserve_one(self, *, preserve: int, tool_name: str | None) -> ToolCallReservation | None:
        if self.tool_calls_available(preserve=preserve, tool_name=tool_name) <= 0:
            return None
        is_search = self.search_policy is not None and tool_name in self.search_policy.tool_names
        is_reserved = tool_name in self.reserved_tool_names
        self._tool_calls_used += 1
        if is_search and self.search_policy is not None:
            self.search_policy.consume(1)
        if is_reserved:
            self._reserved_calls_used += 1
        self._reservation_sequence += 1
        token = ToolCallReservation(
            self._reservation_sequence,
            tool_name,
            is_search,
            is_reserved,
            self.search_policy.epoch if self.search_policy is not None else 0,
        )
        self._active_tool_reservations[token.reservation_id] = token
        return token

    def _reserve_skill_load(self, tool_name: str | None) -> ToolCallReservation | None:
        if self.skill_loads_remaining <= 0:
            return None
        self._skill_loads_used += 1
        self._reservation_sequence += 1
        token = ToolCallReservation(
            self._reservation_sequence,
            tool_name,
            False,
            False,
            0,
            "skill",
        )
        self._active_tool_reservations[token.reservation_id] = token
        return token

    async def reserve_skill_load_with_diagnostics(
        self, tool_name: str | None = None,
    ) -> tuple[ToolCallReservation | None, dict[str, str | int] | None]:
        """Reserve from the separate Skill-load budget, not the data-tool budget."""
        async with self._tool_budget_lock:
            if self.deadline_exceeded():
                return None, {"reason": "deadline"}
            if self.skill_loads_remaining <= 0:
                return None, {
                    "reason": "skill_total",
                    "used": self._skill_loads_used,
                    "limit": self.skill_loads_limit,
                }
            return self._reserve_skill_load(tool_name), None

    def _budget_rejection(self, *, preserve: int, tool_name: str | None) -> dict[str, str | int] | None:
        if self.deadline_exceeded():
            return {"reason": "deadline"}
        if self.tool_calls_remaining <= 0:
            return {"reason": "total_limit", "used": self.tool_calls_used,
                    "limit": self.settings.chat_max_tool_calls_total}
        policy = self.search_policy
        if policy is not None and tool_name in policy.tool_names:
            if policy.used >= policy.total_limit:
                return {"reason": "search_total", "used": policy.used, "limit": policy.total_limit}
            if policy.since_read >= policy.burst_limit:
                return {"reason": "search_burst", "used": policy.since_read, "limit": policy.burst_limit}
        followup = min(max(0, int(preserve)), self.settings.chat_max_tool_calls_total // 2)
        body = self.reserved_calls_remaining if tool_name is not None and tool_name not in self.reserved_tool_names else 0
        if self.tool_calls_remaining <= max(followup, body):
            return {"reason": "body_reserve" if body >= followup else "followup_reserve",
                    "remaining": self.tool_calls_remaining, "reserved": max(followup, body)}
        return None

    async def reserve_tool_call_with_diagnostics(
        self, *, preserve: int = 0, tool_name: str | None = None,
    ) -> tuple[ToolCallReservation | None, dict[str, str | int] | None]:
        """Decide and snapshot denial under the same lock as the reservation."""
        async with self._tool_budget_lock:
            rejection = self._budget_rejection(preserve=preserve, tool_name=tool_name)
            if rejection is not None:
                return None, rejection
            return self._reserve_one(preserve=preserve, tool_name=tool_name), None

    async def reserve_tool_call(self, *, preserve: int = 0, tool_name: str | None = None) -> ToolCallReservation | None:
        async with self._tool_budget_lock:
            return self._reserve_one(preserve=preserve, tool_name=tool_name)

    async def reserve_tool_calls(self, requested: int, *, preserve: int = 0, tool_name: str | None = None) -> int:
        """Compatibility count API; callers must identify the same tool when refunding."""
        accepted = 0
        async with self._tool_budget_lock:
            for _ in range(max(0, int(requested))):
                if self._reserve_one(preserve=preserve, tool_name=tool_name) is None:
                    break
                accepted += 1
        return accepted

    def _settle_reservation(self, token: ToolCallReservation, *, refund: bool) -> bool:
        if self._active_tool_reservations.get(token.reservation_id) is not token:
            return False
        self._active_tool_reservations.pop(token.reservation_id)
        if token.budget_kind == "skill":
            if refund:
                self._skill_loads_used = max(0, self._skill_loads_used - 1)
            return True
        if refund:
            self._tool_calls_used -= 1
            if token.search and self.search_policy is not None:
                self.search_policy.restore(1, epoch=token.search_epoch)
            if token.reserved:
                self._reserved_calls_used -= 1
        return True

    async def settle_tool_reservation(self, token: ToolCallReservation, *, shared: bool = False) -> bool:
        async with self._tool_budget_lock:
            return self._settle_reservation(token, refund=shared)

    async def refund_tool_reservation(self, token: ToolCallReservation) -> bool:
        return await self.settle_tool_reservation(token, shared=True)

    @property
    def reserved_calls_remaining(self) -> int:
        return max(
            0, min(self.reserved_tool_calls, self.settings.chat_max_tool_calls_total // 2) - self._reserved_calls_used
        )

    async def refund_tool_calls(self, refunded: int = 1, *, tool_name: str | None = None) -> int:
        """Refund only active receipts for the named tool; never touch unrelated buckets."""
        count = max(0, int(refunded))
        async with self._tool_budget_lock:
            tokens = [token for token in self._active_tool_reservations.values() if token.tool_name == tool_name][
                :count
            ]
            return sum(self._settle_reservation(token, refund=True) for token in tokens)

    @property
    def skill_loads_limit(self) -> int:
        return max(0, int(getattr(self.settings, "chat_max_skill_loads_total", 3)))

    @property
    def skill_loads_used(self) -> int:
        return self._skill_loads_used

    @property
    def skill_loads_remaining(self) -> int:
        return max(0, self.skill_loads_limit - self._skill_loads_used)

    @property
    def tool_calls_used(self) -> int:
        return self._tool_calls_used

    @property
    def tool_calls_remaining(self) -> int:
        return max(0, self.settings.chat_max_tool_calls_total - self._tool_calls_used)


__all__ = ["AgentExecutionContext", "ToolCallReservation"]
