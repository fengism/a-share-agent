"""FastAPI 认证与授权依赖。"""

from __future__ import annotations

from collections.abc import Callable
from hmac import compare_digest

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.auth.cookies import enforce_cookie_csrf, request_auth_token
from app.api.errors import ApiError
from app.configuration import get_settings
from app.core.request_context import get_current_user as get_bound_user
from app.domain.identity import UserRecord
from app.modules.auth.public import get_user_by_token

UserLookup = Callable[[str], UserRecord | None]
security_scheme = HTTPBearer(auto_error=False)


def resolve_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None,
    *,
    bound_user: UserRecord | None,
    token_lookup: UserLookup,
    cookie_token: str | None = None,
    missing_credentials_detail: str = "未登录",
) -> UserRecord:
    token = credentials.credentials if credentials is not None else cookie_token
    if token is None and bound_user is None:
        raise ApiError(
            status_code=401,
            code="auth.credentials_required",
            message=missing_credentials_detail,
        )
    user = bound_user
    if user is None and token is not None:
        user = token_lookup(token)
    if user is None:
        raise ApiError(
            status_code=401,
            code="auth.session_expired",
            message="登录已过期，请重新登录",
        )
    if not user.get("is_active", 1):
        raise ApiError(
            status_code=403,
            code="auth.account_disabled",
            message="账号已被禁用",
        )
    return user


def ensure_active_user(user: UserRecord) -> UserRecord:
    if not user.get("is_active", 1):
        raise ApiError(
            status_code=403,
            code="auth.account_disabled",
            message="账号已被禁用",
        )
    if user.get("must_change_password"):
        raise ApiError(
            status_code=403,
            code="auth.password_change_required",
            message="请先修改初始密码",
        )
    return user


def ensure_admin(user: UserRecord) -> UserRecord:
    ensure_active_user(user)
    if not user.get("is_admin"):
        raise ApiError(status_code=403, code="auth.admin_required", message="需要管理员权限")
    return user


def ensure_metrics_access(
    credentials: HTTPAuthorizationCredentials | None,
    *,
    configured_key: str,
    provided_key: str,
    bound_user: UserRecord | None,
    token_lookup: UserLookup,
    cookie_token: str | None = None,
) -> None:
    if configured_key and provided_key and compare_digest(provided_key, configured_key):
        return

    user = resolve_authenticated_user(
        credentials,
        bound_user=bound_user,
        token_lookup=token_lookup,
        cookie_token=cookie_token,
        missing_credentials_detail="需要监控访问凭证",
    )
    ensure_admin(user)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserRecord:
    """Resolve the authenticated user from the request token or bound context."""
    token, uses_cookie = request_auth_token(request, credentials)
    enforce_cookie_csrf(request, uses_cookie)
    return resolve_authenticated_user(
        credentials,
        bound_user=get_bound_user(),
        token_lookup=get_user_by_token,
        cookie_token=token if uses_cookie else None,
    )


def require_active_user(user: UserRecord = Depends(get_current_user)) -> UserRecord:
    """Reject authenticated users that still require a password change."""
    return ensure_active_user(user)


def require_admin(user: UserRecord = Depends(require_active_user)) -> UserRecord:
    """Require an active administrator account."""
    return ensure_admin(user)


def require_metrics_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> None:
    """Authorize metrics access with the configured key or an admin session."""
    cookie_token, uses_cookie = request_auth_token(request, credentials)
    # 与 get_current_user 保持一致：这条路径在 API key 不匹配时会回落到 cookie 里的
    # session token，若不做 CSRF 校验，就成了一条无防护的管理员授权路径。
    # 目前挂载的端点都是 GET 所以不可利用，但只要有人给它加个写方法就会变成真实漏洞。
    enforce_cookie_csrf(request, uses_cookie)
    return ensure_metrics_access(
        credentials,
        configured_key=get_settings().metrics_api_key,
        provided_key=request.headers.get("X-Metrics-Key", ""),
        bound_user=get_bound_user(),
        token_lookup=get_user_by_token,
        cookie_token=cookie_token,
    )
