"""ASGI middleware that binds the authenticated user into the request context.

Implemented as a *pure* ASGI middleware (not Starlette's BaseHTTPMiddleware) so
the ContextVar it sets is visible to the endpoint and to any blocking work the
endpoint dispatches via ``asyncio.to_thread`` (which copies the contextvars
context into the worker thread).

The Bearer token is resolved to a user with a single indexed SQLite lookup.
Failures never break the request — an unauthenticated or unresolved request
simply runs with no user bound (global settings apply).
"""
from __future__ import annotations

import logging

from app.utils.request_context import reset_current_user, set_current_user

logger = logging.getLogger(__name__)


class UserContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        token = _extract_bearer(scope.get("headers") or [])
        reset = None
        if token:
            try:
                from app.db import user_store

                # Resolve the user and slide the session's expiry when near the
                # end — any authenticated request keeps an active session alive.
                # The full user dict is bound so auth dependencies can reuse it
                # instead of re-querying the session table.
                user = user_store.resolve_and_renew_session(token)
                if user:
                    reset = set_current_user(user)
            except Exception:
                # Never fail a request because context binding hiccuped.
                logger.warning("绑定用户请求上下文失败", exc_info=True)

        try:
            await self.app(scope, receive, send)
        finally:
            if reset is not None:
                reset_current_user(reset)


def _extract_bearer(headers) -> str | None:
    """Pull the Bearer token from raw ASGI headers (list of (bytes, bytes))."""
    for key, value in headers:
        if key == b"authorization":
            try:
                text = value.decode("latin-1")
            except Exception:
                return None
            if text[:7].lower() == "bearer ":
                return text[7:].strip() or None
            return None
    return None
