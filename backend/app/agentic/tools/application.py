"""Application-owned Tool handlers injected by the runtime composition layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

AsyncHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ApplicationToolHandlers:
    compare_stocks: AsyncHandler
    generate_daily_review: AsyncHandler
    get_industries: AsyncHandler
    research_industry_chain: AsyncHandler
    screen_stocks: AsyncHandler
    analyze_twitter_user: AsyncHandler


_handlers: ApplicationToolHandlers | None = None


def configure_application_tool_handlers(handlers: ApplicationToolHandlers) -> None:
    global _handlers
    _handlers = handlers


def get_application_tool_handlers() -> ApplicationToolHandlers:
    if _handlers is None:
        raise RuntimeError("Application Tool handlers 尚未配置")
    return _handlers


__all__ = [
    "ApplicationToolHandlers",
    "configure_application_tool_handlers",
    "get_application_tool_handlers",
]
