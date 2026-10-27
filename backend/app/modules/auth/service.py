import logging
import secrets
from dataclasses import dataclass
from enum import StrEnum

from app.core.security import (
    WeakPasswordError,
    expiry_in_hours,
    generate_invite_code,
    generate_session_token,
    hash_token,
    invite_expiry,
    validate_password_policy,
    verify_password,
)
from app.domain.identity import UserRecord
from app.infrastructure.persistence import (
    account_store,
    admin_audit_store,
    invite_store,
    session_store,
)
from app.modules.auth import throttle as login_throttle

logger = logging.getLogger(__name__)


class AuthErrorCode(StrEnum):
    REGISTER_THROTTLED = "register_throttled"
    USERNAME_EXISTS = "username_exists"
    INVITE_REQUIRED = "invite_required"
    INVITE_REJECTED = "invite_rejected"
    BOOTSTRAP_CLOSED = "bootstrap_closed"
    LOGIN_THROTTLED = "login_throttled"
    INVALID_CREDENTIALS = "invalid_credentials"
    INCORRECT_PASSWORD = "incorrect_password"
    UNCHANGED_PASSWORD = "unchanged_password"
    WEAK_PASSWORD = "weak_password"
    SETUP_TOKEN_INVALID = "setup_token_invalid"
    INVITE_NOT_FOUND = "invite_not_found"
    INVITE_USED = "invite_used"
    RESET_USER_NOT_FOUND = "reset_user_not_found"
    RESET_THROTTLED = "reset_throttled"
    RESET_TOKEN_INVALID = "reset_token_invalid"
    ACCOUNT_DISABLED = "account_disabled"
    CANNOT_DISABLE_SELF = "cannot_disable_self"
    CANNOT_DELETE_SELF = "cannot_delete_self"
    CANNOT_DEMOTE_SELF = "cannot_demote_self"
    LAST_ADMIN_PROTECTED = "last_admin_protected"
    USER_NOT_FOUND = "user_not_found"


class AuthServiceError(Exception):
    def __init__(self, code: AuthErrorCode, *, retry_after: int = 0, reason: str = ""):
        super().__init__(code.value)
        self.code = code
        self.retry_after = retry_after
        #: 面向用户的补充说明（例如密码强度不达标的具体原因）
        self.reason = reason


@dataclass(frozen=True)
class AuthSession:
    token: str
    user: UserRecord


@dataclass(frozen=True)
class PasswordResetLink:
    username: str
    token: str
    expires_at: str


def _ensure_strong_password(password: str, username: str) -> None:
    """把密码强度校验错误转换成业务错误码。"""
    try:
        validate_password_policy(password, username)
    except WeakPasswordError as error:
        raise AuthServiceError(AuthErrorCode.WEAK_PASSWORD, reason=error.reason) from error


def _ensure_setup_token(provided: str | None) -> None:
    """空库注册首用户时的口令校验（``ADMIN_SETUP_TOKEN``）。

    未配置该口令时保持旧行为（不校验）；配置后必须提供且匹配，
    防止公网实例被他人抢先注册成管理员。
    """
    from app.configuration import get_settings

    expected = (get_settings().admin_setup_token or "").strip()
    if not expected:
        return
    candidate = (provided or "").strip()
    if not candidate or not secrets.compare_digest(candidate, expected):
        raise AuthServiceError(AuthErrorCode.SETUP_TOKEN_INVALID)


def register_account(
    username: str,
    password: str,
    invite_code: str | None,
    client_ip: str,
    user_agent: str = "",
    setup_token: str | None = None,
) -> AuthSession:
    normalized_username = username.strip().lower()
    _ensure_strong_password(password, normalized_username)
    ip_key = f"register-ip:{client_ip}"
    is_first = account_store.count_users() == 0
    if is_first:
        _ensure_setup_token(setup_token)
    if not is_first:
        locked = login_throttle.retry_after(ip_key)
        if locked > 0:
            raise AuthServiceError(AuthErrorCode.REGISTER_THROTTLED, retry_after=locked)

    if account_store.get_user_by_username(normalized_username):
        raise AuthServiceError(AuthErrorCode.USERNAME_EXISTS)

    normalized_invite: str | None = None
    if not is_first:
        normalized_invite = (invite_code or "").strip()
        if not normalized_invite or not invite_store.invite_is_valid(normalized_invite):
            retry_after = login_throttle.record_failure(ip_key)
            raise AuthServiceError(AuthErrorCode.INVITE_REQUIRED, retry_after=retry_after)

    status, user = account_store.create_account(
        normalized_username,
        password,
        is_admin=is_first,
        invite_code=normalized_invite,
    )
    if status == "duplicate":
        raise AuthServiceError(AuthErrorCode.USERNAME_EXISTS)
    if status == "bootstrap_closed":
        raise AuthServiceError(AuthErrorCode.BOOTSTRAP_CLOSED)
    if user is None:
        retry_after = login_throttle.record_failure(ip_key)
        raise AuthServiceError(AuthErrorCode.INVITE_REJECTED, retry_after=retry_after)

    if not user.get("is_admin"):
        login_throttle.reset(ip_key)
    token = session_store.create_session(user["id"], ip_address=client_ip, user_agent=user_agent)
    logger.info("新用户注册: %s (admin=%s)", normalized_username, bool(user.get("is_admin")))
    return AuthSession(token=token, user=user)


def login(username: str, password: str, client_ip: str, user_agent: str = "") -> AuthSession:
    normalized_username = username.strip().lower()
    throttle_keys = [f"combo:{client_ip}:{normalized_username}", f"ip:{client_ip}"]
    locked = max((login_throttle.retry_after(key) for key in throttle_keys), default=0)
    if locked > 0:
        account_store.record_login_audit(
            normalized_username,
            None,
            client_ip,
            user_agent,
            "failed_rate_limited",
            f"locked for {locked}s",
        )
        raise AuthServiceError(AuthErrorCode.LOGIN_THROTTLED, retry_after=locked)

    user = account_store.verify_credentials(normalized_username, password)
    if not user:
        retry_after = max(login_throttle.record_failure(key) for key in throttle_keys)
        account_store.record_login_audit(
            normalized_username,
            None,
            client_ip,
            user_agent,
            "failed_credentials",
            "invalid username or password",
        )
        raise AuthServiceError(AuthErrorCode.INVALID_CREDENTIALS, retry_after=retry_after)

    if not user.get("is_active", 1):
        account_store.record_login_audit(
            normalized_username,
            user.get("id"),
            client_ip,
            user_agent,
            "failed_disabled",
            "account disabled",
        )
        raise AuthServiceError(AuthErrorCode.ACCOUNT_DISABLED)

    for key in throttle_keys:
        login_throttle.reset(key)
    token = session_store.create_session(user["id"], ip_address=client_ip, user_agent=user_agent)
    account_store.record_login_audit(
        normalized_username,
        user.get("id"),
        client_ip,
        user_agent,
        "success",
        "",
    )
    return AuthSession(token=token, user=user)


def get_user_by_token(token: str) -> UserRecord | None:
    return session_store.get_user_by_token(token)


def logout(token: str | None) -> None:
    if token:
        session_store.delete_session(token)


def change_password(
    user: UserRecord,
    old_password: str,
    new_password: str,
    current_token: str | None,
) -> int:
    if not verify_password(old_password, user.get("password_hash", "")):
        raise AuthServiceError(AuthErrorCode.INCORRECT_PASSWORD)
    if old_password == new_password:
        raise AuthServiceError(AuthErrorCode.UNCHANGED_PASSWORD)
    _ensure_strong_password(new_password, str(user.get("username", "")))

    keep_token_hash = hash_token(current_token) if current_token else None
    revoked = account_store.change_password_and_revoke_sessions(
        user["id"],
        new_password,
        keep_token_hash,
    )
    logger.info("用户修改密码: id=%s, 其它会话已吊销=%s", user["id"], revoked)
    return revoked


def needs_setup() -> bool:
    return account_store.count_users() == 0


def requires_setup_token() -> bool:
    """空库注册是否需要 ``ADMIN_SETUP_TOKEN``（前端据此显示输入框）。"""
    from app.configuration import get_settings

    return bool((get_settings().admin_setup_token or "").strip())


def create_invite(admin_id: int, expires_in_days: int | None) -> dict:
    expires_at = invite_expiry(expires_in_days) if expires_in_days else None
    invite = invite_store.create_invite(
        admin_id,
        generate_invite_code(),
        expires_at=expires_at,
    )
    admin_audit_store.record_admin_action(
        action="invite.create",
        target_type="invite",
        target_id=str(invite.get("code", "")),
        target_label=f"expires_in_days={expires_in_days or 'never'}",
    )
    return invite


def list_invites(admin_id: int | None = None) -> list[dict]:
    return invite_store.list_invites()


def revoke_invite(code: str, admin_id: int | None = None) -> None:
    status = invite_store.revoke_invite(code)
    if status == "not_found":
        raise AuthServiceError(AuthErrorCode.INVITE_NOT_FOUND)
    if status == "used":
        raise AuthServiceError(AuthErrorCode.INVITE_USED)
    admin_audit_store.record_admin_action(
        action="invite.revoke",
        target_type="invite",
        target_id=code,
    )


def cleanup_expired_invites() -> int:
    deleted = invite_store.cleanup_expired_invites()
    logger.info("清理过期未使用的邀请码: %s 个", deleted)
    admin_audit_store.record_admin_action(
        action="invite.cleanup",
        target_type="invite",
        details={"deleted": deleted},
    )
    return deleted


def create_password_reset_link(
    username: str,
    admin_id: int,
    expires_in_hours: int,
) -> PasswordResetLink:
    target = account_store.get_user_by_username(username.strip())
    if not target:
        raise AuthServiceError(AuthErrorCode.RESET_USER_NOT_FOUND)

    token = generate_session_token()
    expires_at = expiry_in_hours(expires_in_hours)
    invite_store.create_password_reset(target["id"], admin_id, token, expires_at)
    logger.info("管理员签发密码重置链接: target=%s by admin=%s", target["id"], admin_id)
    admin_audit_store.record_admin_action(
        action="user.reset_link",
        target_type="user",
        target_id=target["id"],
        target_label=str(target.get("username", "")),
        details={"expires_in_hours": expires_in_hours},
    )
    return PasswordResetLink(
        username=target["username"],
        token=token,
        expires_at=expires_at,
    )


def reset_password(token: str, new_password: str, client_ip: str) -> None:
    _ensure_strong_password(new_password, "")
    ip_key = f"reset-ip:{client_ip}"
    locked = login_throttle.retry_after(ip_key)
    if locked > 0:
        raise AuthServiceError(AuthErrorCode.RESET_THROTTLED, retry_after=locked)

    user_id = account_store.reset_password_with_token(token, new_password)
    if user_id is None:
        retry_after = login_throttle.record_failure(ip_key)
        raise AuthServiceError(AuthErrorCode.RESET_TOKEN_INVALID, retry_after=retry_after)

    login_throttle.reset(ip_key)
    logger.info("密码经重置链接更新: user=%s", user_id)


def list_sessions(user: UserRecord, current_token: str | None) -> list[dict[str, object]]:
    """当前用户的登录设备列表（含"当前会话"标记）。"""
    return session_store.list_user_sessions(user["id"], current_token=current_token)


def revoke_own_session(user: UserRecord, session_handle: str, current_token: str | None) -> bool:
    """撤销当前用户自己的一个会话；成功后写一条审计记录。"""
    revoked = session_store.revoke_user_session(user["id"], session_handle)
    if revoked:
        admin_audit_store.record_admin_action(
            action="session.revoke",
            target_type="user",
            target_id=user["id"],
            target_label=str(user.get("username", "")),
            details={"session": session_handle[:12], "self": True},
        )
    return revoked


def list_users() -> list[UserRecord]:
    return account_store.list_users()


def update_user_status(current_admin_id: int, target_user_id: int, is_active: bool) -> UserRecord:
    target = account_store.get_user_by_id(target_user_id)
    if not target:
        raise AuthServiceError(AuthErrorCode.USER_NOT_FOUND)
    if current_admin_id == target_user_id and not is_active:
        raise AuthServiceError(AuthErrorCode.CANNOT_DISABLE_SELF)
    if not is_active and target.get("is_admin") and account_store.count_active_admins() <= 1:
        raise AuthServiceError(AuthErrorCode.LAST_ADMIN_PROTECTED)

    account_store.set_user_active(target_user_id, is_active)
    updated = account_store.get_user_by_id(target_user_id)
    assert updated is not None
    logger.info("管理员(id=%s) 修改用户(id=%s, username=%s) 状态为 is_active=%s", current_admin_id, target_user_id, target.get("username"), is_active)
    admin_audit_store.record_admin_action(
        action="user.status",
        target_type="user",
        target_id=target_user_id,
        target_label=str(target.get("username", "")),
        details={"is_active": bool(is_active)},
    )
    return updated


def update_user_role(current_admin_id: int, target_user_id: int, is_admin: bool) -> UserRecord:
    target = account_store.get_user_by_id(target_user_id)
    if not target:
        raise AuthServiceError(AuthErrorCode.USER_NOT_FOUND)
    if current_admin_id == target_user_id and not is_admin:
        raise AuthServiceError(AuthErrorCode.CANNOT_DEMOTE_SELF)
    if not is_admin and target.get("is_admin") and account_store.count_active_admins() <= 1:
        raise AuthServiceError(AuthErrorCode.LAST_ADMIN_PROTECTED)

    account_store.set_user_role(target_user_id, is_admin)
    updated = account_store.get_user_by_id(target_user_id)
    assert updated is not None
    logger.info("管理员(id=%s) 修改用户(id=%s, username=%s) 角色为 is_admin=%s", current_admin_id, target_user_id, target.get("username"), is_admin)
    admin_audit_store.record_admin_action(
        action="user.role",
        target_type="user",
        target_id=target_user_id,
        target_label=str(target.get("username", "")),
        details={"is_admin": bool(is_admin)},
    )
    return updated


def delete_user(current_admin_id: int, target_user_id: int) -> None:
    target = account_store.get_user_by_id(target_user_id)
    if not target:
        raise AuthServiceError(AuthErrorCode.USER_NOT_FOUND)
    if current_admin_id == target_user_id:
        raise AuthServiceError(AuthErrorCode.CANNOT_DELETE_SELF)
    if target.get("is_admin") and account_store.count_active_admins() <= 1:
        raise AuthServiceError(AuthErrorCode.LAST_ADMIN_PROTECTED)

    account_store.delete_user(target_user_id)
    logger.warning("管理员(id=%s) 删除了用户(id=%s, username=%s)", current_admin_id, target_user_id, target.get("username"))
    admin_audit_store.record_admin_action(
        action="user.delete",
        target_type="user",
        target_id=target_user_id,
        target_label=str(target.get("username", "")),
    )


def revoke_user_sessions(target_user_id: int) -> int:
    target = account_store.get_user_by_id(target_user_id)
    if not target:
        raise AuthServiceError(AuthErrorCode.USER_NOT_FOUND)
    revoked = account_store.revoke_user_sessions(target_user_id)
    logger.info("强制踢出用户(id=%s, username=%s) 所有会话, 撤销数=%s", target_user_id, target.get("username"), revoked)
    admin_audit_store.record_admin_action(
        action="user.revoke_sessions",
        target_type="user",
        target_id=target_user_id,
        target_label=str(target.get("username", "")),
        details={"revoked": revoked},
    )
    return revoked


def update_user_must_change_password(
    current_admin_id: int, target_user_id: int, must_change: bool
) -> UserRecord:
    target = account_store.get_user_by_id(target_user_id)
    if not target:
        raise AuthServiceError(AuthErrorCode.USER_NOT_FOUND)

    account_store.set_user_must_change_password(target_user_id, must_change)
    updated = account_store.get_user_by_id(target_user_id)
    assert updated is not None
    logger.info(
        "管理员(id=%s) 修改用户(id=%s, username=%s) 强制改密标记: must_change_password=%s",
        current_admin_id,
        target_user_id,
        target.get("username"),
        must_change,
    )
    admin_audit_store.record_admin_action(
        action="user.must_change_password",
        target_type="user",
        target_id=target_user_id,
        target_label=str(target.get("username", "")),
        details={"must_change_password": bool(must_change)},
    )
    return updated


def get_login_audit_logs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    username: str | None = None,
    user_id: int | None = None,
) -> tuple[list[dict], int]:
    return account_store.list_login_audit_logs(
        limit=limit,
        offset=offset,
        status=status,
        username=username,
        user_id=user_id,
    )
