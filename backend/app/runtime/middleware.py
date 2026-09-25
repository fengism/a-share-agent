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
import re
import time
from collections.abc import Sequence
from http.cookies import SimpleCookie
from uuid import uuid4

from starlette.responses import Response

from app.api.auth.cookies import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    set_auth_cookies,
)
from app.configuration import get_effective_settings, get_settings
from app.configuration.crypto import ConfigEncryptionError
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.metrics import metrics
from app.core.request_context import (
    bind_settings_cache,
    reset_current_request_id,
    reset_current_user,
    reset_settings_cache,
    set_current_request_id,
    set_current_user,
)

logger = logging.getLogger(__name__)


class UserContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        token, uses_cookie, csrf_token = _extract_auth_context(scope.get("headers") or [])
        settings_reset = bind_settings_cache()
        reset = None
        renewed = False
        if token:
            try:
                from app.infrastructure.persistence import session_store

                user, renewed = await call_blocking(
                    session_store.resolve_and_renew_session_with_status,
                    token,
                    semaphore=database_semaphore,
                )
                if user:
                    scope.setdefault("state", {})["user_id"] = user["id"]
                    reset = set_current_user(user)
                    try:
                        await call_blocking(
                            get_effective_settings,
                            semaphore=database_semaphore,
                        )
                    except ConfigEncryptionError:
                        logger.warning(
                            "预加载用户配置失败，将由业务接口返回配置错误 user_id=%s",
                            user["id"],
                            exc_info=True,
                        )
            except Exception:
                # Never fail a request because context binding hiccuped.
                logger.warning("绑定用户请求上下文失败", exc_info=True)

        async def send_with_session_renewal(message):
            if (
                renewed
                and uses_cookie
                and token
                and message.get("type") == "http.response.start"
                and not _sets_session_cookie(message.get("headers", []))
            ):
                cookie_response = Response()
                set_auth_cookies(
                    cookie_response,
                    token,
                    secure=get_settings().auth_cookie_secure,
                    csrf_token=csrf_token,
                )
                renewal_headers = [header for header in cookie_response.raw_headers if header[0] == b"set-cookie"]
                message = {
                    **message,
                    "headers": [*message.get("headers", []), *renewal_headers],
                }
            await send(message)

        try:
            await self.app(scope, receive, send_with_session_renewal)
        finally:
            if reset is not None:
                reset_current_user(reset)
            reset_settings_cache(settings_reset)


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_QUIET_POLL_PATHS = frozenset({"/api/workflows/active"})
_SLOW_POLL_MS = 1000


class RequestObservabilityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_from_headers(scope.get("headers") or [])
        scope.setdefault("state", {})["request_id"] = request_id
        request_id_reset = set_current_request_id(request_id)
        started_at = time.perf_counter()
        status = 500
        failed = False

        async def send_with_request_id(message):
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status", 500))
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except BaseException:
            # A stream may fail after sending 200; never demote that failure.
            failed = True
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            route = scope.get("route")
            request_path = scope.get("path", "")
            route_path = getattr(route, "path", None)
            metric_path = route_path or "<unmatched>"
            method = scope.get("method", "")
            user_id = scope.get("state", {}).get("user_id")
            level = logging.INFO
            if failed or status >= 500:
                level = logging.ERROR
            elif status >= 400:
                level = logging.WARNING
            elif method == "GET" and request_path in _QUIET_POLL_PATHS and 200 <= status < 300:
                # Only short polling requests are quiet; long-lived SSE is not a slow poll.
                level = logging.WARNING if duration_ms >= _SLOW_POLL_MS else logging.DEBUG
            try:
                metrics.record_request(method, metric_path, status, duration_ms)
                logger.log(
                    level,
                    "request %s request_id=%s method=%s path=%s route=%s status=%s duration_ms=%.2f user_id=%s",
                    "failed" if failed else "completed",
                    request_id,
                    method,
                    request_path,
                    metric_path,
                    status,
                    duration_ms,
                    user_id,
                )
            finally:
                reset_current_request_id(request_id_reset)


def _extract_auth_context(
    headers: Sequence[tuple[bytes, bytes]],
) -> tuple[str | None, bool, str | None]:
    """Pull the preferred auth token and cookie metadata from ASGI headers."""
    for key, value in headers:
        if key.lower() == b"authorization":
            try:
                text = value.decode("latin-1")
            except Exception:
                return None, False, None
            if text[:7].lower() == "bearer ":
                return text[7:].strip() or None, False, None
            return None, False, None
    cookies = SimpleCookie()
    for key, value in headers:
        if key.lower() != b"cookie":
            continue
        try:
            cookies.load(value.decode("latin-1"))
        except Exception:
            return None, False, None
    session_morsel = cookies.get(SESSION_COOKIE_NAME)
    csrf_morsel = cookies.get(CSRF_COOKIE_NAME)
    token = session_morsel.value if session_morsel is not None else None
    csrf_token = csrf_morsel.value if csrf_morsel is not None else None
    return token or None, bool(token), csrf_token or None


def _sets_session_cookie(headers: Sequence[tuple[bytes, bytes]]) -> bool:
    prefix = f"{SESSION_COOKIE_NAME}=".encode()
    return any(key.lower() == b"set-cookie" and value.lstrip().startswith(prefix) for key, value in headers)


def _request_id_from_headers(headers: Sequence[tuple[bytes, bytes]]) -> str:
    for key, value in headers:
        if key.lower() != b"x-request-id":
            continue
        try:
            request_id = value.decode("ascii")
        except UnicodeDecodeError:
            break
        if _REQUEST_ID_PATTERN.fullmatch(request_id):
            return request_id
        break
    return uuid4().hex
