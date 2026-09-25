"""账户注册、登录、会话和管理员邀请 HTTP API。"""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

import app.modules.auth.public as auth_service
from app.api.auth.cookies import (
    clear_auth_cookies,
    enforce_cookie_csrf,
    request_auth_token,
    set_auth_cookies,
)
from app.api.auth.dependencies import get_current_user, require_admin, security_scheme
from app.api.auth.http import auth_error_to_http, client_ip, invite_out, user_out
from app.api.errors import ApiError
from app.configuration import get_settings
from app.core.security import now_ts
from app.domain.identity import AuthenticatedUser, UserRecord
from app.modules.auth.public import (
    AdminResetLinkRequest,
    AuthResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    CleanupInvitesResponse,
    CreateInviteRequest,
    InviteOut,
    LoginAuditLogItem,
    LoginAuditLogsResponse,
    LoginRequest,
    NeedsSetupResponse,
    OkResponse,
    RegisterRequest,
    ResetLinkOut,
    ResetPasswordRequest,
    RevokeSessionsResponse,
    UpdateMustChangePasswordRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserOut,
)

router = APIRouter()


def _user_out(u: AuthenticatedUser) -> UserOut:
    return user_out(u)


def _http_error(error: auth_service.AuthServiceError) -> ApiError:
    return auth_error_to_http(error)


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, request: Request, response: Response) -> AuthResponse:
    try:
        session = auth_service.register_account(
            req.username,
            req.password,
            req.invite_code,
            _client_ip(request),
        )
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    set_auth_cookies(response, session.token, secure=get_settings().auth_cookie_secure)
    return AuthResponse(token=session.token, user=_user_out(session.user))


def _client_ip(request: Request) -> str:
    """Best-effort client IP.

    Honours X-Forwarded-For only when ``trust_proxy_headers`` is enabled (i.e.
    the app runs behind a trusted reverse proxy). When disabled, XFF is ignored
    so a directly-exposed instance can't be tricked into trusting a spoofed IP
    for throttling / lockout purposes.
    """
    return client_ip(request, trust_proxy_headers=get_settings().trust_proxy_headers)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, response: Response) -> AuthResponse:
    try:
        user_agent = request.headers.get("user-agent", "")
        session = auth_service.login(
            req.username, req.password, _client_ip(request), user_agent=user_agent
        )
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    set_auth_cookies(response, session.token, secure=get_settings().auth_cookie_secure)
    return AuthResponse(token=session.token, user=_user_out(session.user))


@router.post("/logout", response_model=OkResponse)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> OkResponse:
    token, uses_cookie = request_auth_token(request, credentials)
    enforce_cookie_csrf(request, uses_cookie)
    auth_service.logout(token)
    clear_auth_cookies(response, secure=get_settings().auth_cookie_secure)
    return OkResponse()


@router.get("/me", response_model=UserOut)
def me(user: AuthenticatedUser = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    user: UserRecord = Depends(get_current_user),
) -> ChangePasswordResponse:
    """Change the current user's password after verifying the old one, then
    revoke every other session (the current device stays logged in)."""
    try:
        token, _ = request_auth_token(request, credentials)
        revoked = auth_service.change_password(
            user,
            req.old_password,
            req.new_password,
            token,
        )
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return ChangePasswordResponse(revoked_sessions=revoked)


@router.get("/needs-setup", response_model=NeedsSetupResponse)
def needs_setup() -> NeedsSetupResponse:
    """Whether the instance has no users yet (first registration becomes admin)."""
    return NeedsSetupResponse(needs_setup=auth_service.needs_setup())


def _invite_out(inv: dict) -> InviteOut:
    return invite_out(inv, current_timestamp=now_ts())


@router.post("/invite", response_model=InviteOut)
def create_invite(
    req: CreateInviteRequest | None = None,
    admin: AuthenticatedUser = Depends(require_admin),
) -> InviteOut:
    expires_in_days = req.expires_in_days if req else None
    return _invite_out(auth_service.create_invite(admin["id"], expires_in_days))


@router.get("/invites", response_model=list[InviteOut])
def list_invites(admin: AuthenticatedUser = Depends(require_admin)) -> list[InviteOut]:
    return [_invite_out(invite) for invite in auth_service.list_invites(admin["id"])]


@router.delete("/invite/{code}", response_model=OkResponse)
def revoke_invite(code: str, admin: AuthenticatedUser = Depends(require_admin)) -> OkResponse:
    """Cancel an unused invite. Already-used invites cannot be revoked."""
    try:
        auth_service.revoke_invite(code, admin["id"])
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return OkResponse()


@router.post("/invites/cleanup-expired", response_model=CleanupInvitesResponse)
def cleanup_expired_invites(
    admin: AuthenticatedUser = Depends(require_admin),
) -> CleanupInvitesResponse:
    """Admin: purge expired and unused invites."""
    count = auth_service.cleanup_expired_invites()
    return CleanupInvitesResponse(cleaned_count=count)


@router.post("/admin/reset-link", response_model=ResetLinkOut)
def admin_reset_link(
    req: AdminResetLinkRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> ResetLinkOut:
    """Admin issues a one-time, expiring password-reset token for a user.

    The token is shown to the admin once (to hand over out-of-band); only its
    hash is stored. No email infrastructure is involved.
    """
    try:
        reset_link = auth_service.create_password_reset_link(
            req.username,
            admin["id"],
            req.expires_in_hours,
        )
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return ResetLinkOut(
        username=reset_link.username,
        token=reset_link.token,
        expires_at=reset_link.expires_at,
    )


@router.post("/reset-password", response_model=OkResponse)
def reset_password(req: ResetPasswordRequest, request: Request) -> OkResponse:
    """Public: redeem a reset token to set a new password.

    On success every session for that user is revoked (they forgot the
    password), so all devices must log in again. Throttled by IP.
    """
    try:
        auth_service.reset_password(req.token, req.new_password, _client_ip(request))
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return OkResponse()


@router.get("/admin/users", response_model=list[UserOut])
def list_users(admin: AuthenticatedUser = Depends(require_admin)) -> list[UserOut]:
    """Admin: list all registered accounts."""
    return [_user_out(u) for u in auth_service.list_users()]


@router.put("/admin/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: int,
    req: UpdateUserStatusRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> UserOut:
    """Admin: enable or disable a user account."""
    try:
        user = auth_service.update_user_status(admin["id"], user_id, req.is_active)
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return _user_out(user)


@router.put("/admin/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int,
    req: UpdateUserRoleRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> UserOut:
    """Admin: promote or demote a user's admin role."""
    try:
        user = auth_service.update_user_role(admin["id"], user_id, req.is_admin)
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return _user_out(user)


@router.delete("/admin/users/{user_id}", response_model=OkResponse)
def delete_user(
    user_id: int,
    admin: AuthenticatedUser = Depends(require_admin),
) -> OkResponse:
    """Admin: delete a user account and purge all their sessions/configs."""
    try:
        auth_service.delete_user(admin["id"], user_id)
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return OkResponse()


@router.post("/admin/users/{user_id}/revoke-sessions", response_model=RevokeSessionsResponse)
def revoke_user_sessions(
    user_id: int,
    admin: AuthenticatedUser = Depends(require_admin),
) -> RevokeSessionsResponse:
    """Admin: force revoke all active sessions for a user."""
    try:
        revoked = auth_service.revoke_user_sessions(user_id)
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return RevokeSessionsResponse(revoked_sessions=revoked)


@router.post("/admin/users/{user_id}/must-change-password", response_model=UserOut)
def update_user_must_change_password(
    user_id: int,
    req: UpdateMustChangePasswordRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> UserOut:
    """Admin: toggle whether a user must change their password on next login."""
    try:
        user = auth_service.update_user_must_change_password(
            admin["id"], user_id, req.must_change_password
        )
    except auth_service.AuthServiceError as error:
        raise _http_error(error) from error
    return _user_out(user)


@router.get("/admin/audit-logs", response_model=LoginAuditLogsResponse)
def get_login_audit_logs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    username: str | None = None,
    admin: AuthenticatedUser = Depends(require_admin),
) -> LoginAuditLogsResponse:
    """Admin: list login audit log records with filtering and pagination."""
    logs, total = auth_service.get_login_audit_logs(
        limit=min(limit, 200),
        offset=offset,
        status=status,
        username=username,
    )
    return LoginAuditLogsResponse(
        items=[LoginAuditLogItem(**log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )

