"""Cookie 会话与 CSRF HTTP 适配。"""

from __future__ import annotations

import secrets
from hmac import compare_digest

from fastapi import Request, Response

from app.api.errors import ApiError
from app.configuration import get_settings
from app.core.security import SESSION_TTL_DAYS

SESSION_COOKIE_NAME = "a_share_session"
CSRF_COOKIE_NAME = "a_share_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _is_secure_request(*, scheme: str, forwarded_proto: str | None, trust_proxy_headers: bool) -> bool:
    """判断当前请求是否为 HTTPS。

    仅当显式信任代理头时才采信 X-Forwarded-Proto，避免直连实例被伪造头欺骗。
    """
    if trust_proxy_headers and forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return scheme == "https"


def resolve_secure_cookie(request: Request, configured: bool) -> bool:
    """综合显式配置与请求协议决定是否给会话 Cookie 加 Secure。

    运维忘记设置 auth_cookie_secure 时，HTTPS 请求仍应拿到 Secure Cookie；
    本地 HTTP 开发则保持不加 Secure，否则浏览器不会回传 Cookie。
    """
    if configured:
        return True
    return _is_secure_request(
        scheme=request.url.scheme,
        forwarded_proto=request.headers.get("x-forwarded-proto"),
        trust_proxy_headers=get_settings().trust_proxy_headers,
    )


def request_auth_token(request: Request, credentials) -> tuple[str | None, bool]:
    bearer_token = getattr(credentials, "credentials", None)
    if bearer_token:
        return bearer_token, False
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    return cookie_token, bool(cookie_token)


def enforce_cookie_csrf(request: Request, uses_cookie: bool) -> None:
    if not uses_cookie or request.method.upper() in SAFE_METHODS:
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get(CSRF_HEADER_NAME, "")
    if not cookie_token or not header_token or not compare_digest(cookie_token, header_token):
        raise ApiError(status_code=403, code="auth.csrf_failed", message="CSRF 校验失败")


def set_auth_cookies(
    response: Response,
    session_token: str,
    *,
    secure: bool,
    csrf_token: str | None = None,
) -> None:
    max_age = SESSION_TTL_DAYS * 24 * 60 * 60
    csrf_token = csrf_token or secrets.token_urlsafe(32)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, *, secure: bool) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )
