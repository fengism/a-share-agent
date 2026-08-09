"""Per-request context: the currently authenticated user.

The full user record is bound once per HTTP request by ``UserContextMiddleware``
(a pure ASGI middleware, which shares the endpoint's task context). It is read
by ``app.configuration.get_effective_settings`` (via the user id) so per-user private
config can be overlaid transparently, and by the auth dependency to avoid a
second session lookup. Because ``asyncio.to_thread`` copies the current
contextvars context into the worker thread, the bound user also propagates to
blocking provider / LLM / Feishu / Notion calls dispatched via
``app.core.concurrency.rate_limiter.call_blocking``.

Outside any request (startup background tasks, CLI) the value is ``None`` and
callers fall back to the global instance settings.
"""
from __future__ import annotations

import contextvars
import threading
from collections.abc import Callable
from typing import TypeVar, cast

from app.contracts.auth import UserRecord

T = TypeVar("T")
_UNSET = object()


class _RequestSettingsCache:
    def __init__(self) -> None:
        self.value: object = _UNSET
        self.lock = threading.Lock()


# NOTE: the annotation stays lazy via ``from __future__ import annotations`` so
# this module imports even on Python < 3.10; the project targets 3.11+.
#
# The middleware resolves the Bearer token to a full user row once per request
# and binds the typed record here, so downstream auth dependencies can reuse it
# instead of re-querying the session table on every request.
current_user: contextvars.ContextVar[UserRecord | None] = contextvars.ContextVar(
    "current_user", default=None
)
current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)
current_settings_cache: contextvars.ContextVar[_RequestSettingsCache | None] = contextvars.ContextVar(
    "current_settings_cache", default=None
)


def set_current_user(user: UserRecord | None) -> contextvars.Token[UserRecord | None]:
    """Bind the current user record; returns a token to pass to reset_current_user."""
    return current_user.set(user)


def reset_current_user(token: contextvars.Token[UserRecord | None]) -> None:
    """Restore the previous value using the token from set_current_user."""
    current_user.reset(token)


def get_current_user() -> UserRecord | None:
    """Return the current request's authenticated user record, or None when unbound."""
    return current_user.get()


def get_current_user_id() -> int | None:
    """Return the current request's user id, or None when unbound."""
    user = current_user.get()
    return user["id"] if user else None


def set_current_request_id(request_id: str):
    return current_request_id.set(request_id)


def reset_current_request_id(token) -> None:
    current_request_id.reset(token)


def get_current_request_id() -> str | None:
    return current_request_id.get()


def bind_settings_cache():
    """为当前请求绑定一个可跨协程和工作线程共享的配置缓存。"""
    return current_settings_cache.set(_RequestSettingsCache())


def reset_settings_cache(token) -> None:
    """恢复进入当前请求前的配置缓存上下文。"""
    current_settings_cache.reset(token)


def invalidate_settings_cache() -> None:
    """使当前请求已经合并的生效配置失效。"""
    cache = current_settings_cache.get()
    if cache is None:
        return
    with cache.lock:
        cache.value = _UNSET


def get_or_create_effective_settings(factory: Callable[[], T]) -> T:
    """读取当前请求缓存；未绑定请求上下文时直接调用 factory。"""
    cache = current_settings_cache.get()
    if cache is None:
        return factory()
    if cache.value is _UNSET:
        with cache.lock:
            if cache.value is _UNSET:
                cache.value = factory()
    return cast(T, cache.value)
