"""Per-request context: the currently authenticated user.

The full user dict is bound once per HTTP request by ``UserContextMiddleware``
(a pure ASGI middleware, which shares the endpoint's task context). It is read
by ``app.config.get_effective_settings`` (via the user id) so per-user private
config can be overlaid transparently, and by the auth dependency to avoid a
second session lookup. Because ``asyncio.to_thread`` copies the current
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
#
# The middleware resolves the Bearer token to a full user row once per request
# and binds the whole dict here, so downstream auth dependencies can reuse it
# instead of re-querying the session table on every request.
current_user: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "current_user", default=None
)


def set_current_user(user: dict | None):
    """Bind the current user dict; returns a token to pass to reset_current_user."""
    return current_user.set(user)


def reset_current_user(token) -> None:
    """Restore the previous value using the token from set_current_user."""
    current_user.reset(token)


def get_current_user():
    """Return the current request's authenticated user dict, or None when unbound."""
    return current_user.get()


def get_current_user_id():
    """Return the current request's user id, or None when unbound."""
    user = current_user.get()
    return user["id"] if user else None
