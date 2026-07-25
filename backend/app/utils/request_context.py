"""Per-request context: the currently authenticated user id.

The value is bound once per HTTP request by ``UserContextMiddleware`` (a pure
ASGI middleware, which shares the endpoint's task context) and read by
``app.config.get_effective_settings`` so that per-user private config can be
overlaid transparently. Because ``asyncio.to_thread`` copies the current
contextvars context into the worker thread, the bound user also propagates to
blocking provider / LLM / Feishu / Notion calls dispatched via
``app.utils.rate_limiter.call_blocking``.

Outside any request (startup background tasks, CLI) the value is ``None`` and
callers fall back to the global instance settings.
"""
from __future__ import annotations

import contextvars

# NOTE: the annotation stays lazy via ``from __future__ import annotations`` so
# this module imports even on Python < 3.10; the project targets 3.11+.
current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "current_user_id", default=None
)


def set_current_user_id(user_id: int | None):
    """Bind the current user id; returns a token to pass to reset_current_user_id."""
    return current_user_id.set(user_id)


def reset_current_user_id(token) -> None:
    """Restore the previous value using the token from set_current_user_id."""
    current_user_id.reset(token)


def get_current_user_id():
    """Return the current request's user id, or None when unbound."""
    return current_user_id.get()
