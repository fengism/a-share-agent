"""认证业务结果到 HTTP 响应的转换。"""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.api.errors import ApiError
from app.domain.identity import AuthenticatedUser
from app.modules.auth.public import AuthErrorCode, AuthServiceError, InviteOut, UserOut


def user_out(user: AuthenticatedUser) -> UserOut:
    return UserOut(
        id=user["id"],
        username=user["username"],
        is_admin=bool(user["is_admin"]),
        must_change_password=bool(user.get("must_change_password", 0)),
    )


def invite_out(invite: dict[str, object], *, current_timestamp: str) -> InviteOut:
    used = invite["used_by"] is not None
    expires_at = cast(str | None, invite.get("expires_at"))
    expired = (
        (not used)
        and expires_at is not None
        and bool(expires_at)
        and expires_at < current_timestamp
    )
    return InviteOut(
        code=cast(str, invite["code"]),
        used=used,
        expired=expired,
        created_at=cast(str | None, invite.get("created_at")),
        expires_at=expires_at,
    )


def client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return str(forwarded_for).split(",")[0].strip()
    return str(request.client.host) if request.client else "unknown"


def auth_error_to_http(error: AuthServiceError) -> ApiError:
    code = error.code
    retry_after = error.retry_after

    def response(status_code: int, message: str, headers: dict[str, str] | None = None) -> ApiError:
        return ApiError(
            status_code=status_code,
            code=f"auth.{code.value}",
            message=message,
            headers=headers,
        )

    if code == AuthErrorCode.REGISTER_THROTTLED:
        return response(
            429,
            f"尝试过于频繁，请 {retry_after} 秒后再试",
            {"Retry-After": str(retry_after)},
        )
    if code == AuthErrorCode.USERNAME_EXISTS:
        return response(409, "用户名已存在")
    if code == AuthErrorCode.INVITE_REQUIRED:
        detail = "需要有效的邀请码"
        if retry_after > 0:
            detail = f"邀请码错误次数过多，请 {retry_after} 秒后再试"
        return response(403 if retry_after == 0 else 429, detail)
    if code == AuthErrorCode.INVITE_REJECTED:
        detail = "邀请码无效或已被使用"
        if retry_after > 0:
            detail = f"邀请码错误次数过多，请 {retry_after} 秒后再试"
        return response(403 if retry_after == 0 else 429, detail)
    if code == AuthErrorCode.BOOTSTRAP_CLOSED:
        return response(409, "系统已完成初始化，请使用邀请码注册")
    if code == AuthErrorCode.LOGIN_THROTTLED:
        return response(
            429,
            f"尝试过于频繁，请 {retry_after} 秒后再试",
            {"Retry-After": str(retry_after)},
        )
    if code == AuthErrorCode.INVALID_CREDENTIALS:
        if retry_after > 0:
            return response(
                429,
                f"失败次数过多，已临时锁定，请 {retry_after} 秒后再试",
                {"Retry-After": str(retry_after)},
            )
        return response(401, "用户名或密码错误")
    if code == AuthErrorCode.INCORRECT_PASSWORD:
        return response(400, "原密码错误")
    if code == AuthErrorCode.UNCHANGED_PASSWORD:
        return response(400, "新密码不能与原密码相同")
    if code == AuthErrorCode.INVITE_NOT_FOUND:
        return response(404, "邀请码不存在")
    if code == AuthErrorCode.INVITE_USED:
        return response(409, "该邀请码已被使用，无法撤销")
    if code == AuthErrorCode.RESET_USER_NOT_FOUND:
        return response(404, "用户不存在")
    if code in {
        AuthErrorCode.RESET_THROTTLED,
        AuthErrorCode.RESET_TOKEN_INVALID,
    } and retry_after > 0:
        return response(
            429,
            f"尝试过于频繁，请 {retry_after} 秒后再试",
            {"Retry-After": str(retry_after)},
        )
    if code == AuthErrorCode.RESET_TOKEN_INVALID:
        return response(400, "重置链接无效或已过期")
    raise RuntimeError(f"未处理的认证服务错误: {code}")
