import logging
from dataclasses import dataclass
from enum import StrEnum

from app.core.security import (
    expiry_in_hours,
    generate_invite_code,
    generate_session_token,
    hash_token,
    invite_expiry,
    verify_password,
)
from app.domain.identity import UserRecord
from app.infrastructure.persistence import account_store, invite_store, session_store
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
    INVITE_NOT_FOUND = "invite_not_found"
    INVITE_USED = "invite_used"
    RESET_USER_NOT_FOUND = "reset_user_not_found"
    RESET_THROTTLED = "reset_throttled"
    RESET_TOKEN_INVALID = "reset_token_invalid"


class AuthServiceError(Exception):
    def __init__(self, code: AuthErrorCode, *, retry_after: int = 0):
        super().__init__(code.value)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class AuthSession:
    token: str
    user: UserRecord


@dataclass(frozen=True)
class PasswordResetLink:
    username: str
    token: str
    expires_at: str


def register_account(
    username: str,
    password: str,
    invite_code: str | None,
    client_ip: str,
) -> AuthSession:
    ip_key = f"register-ip:{client_ip}"
    is_first = account_store.count_users() == 0
    if not is_first:
        locked = login_throttle.retry_after(ip_key)
        if locked > 0:
            raise AuthServiceError(AuthErrorCode.REGISTER_THROTTLED, retry_after=locked)

    if account_store.get_user_by_username(username):
        raise AuthServiceError(AuthErrorCode.USERNAME_EXISTS)

    normalized_invite: str | None = None
    if not is_first:
        normalized_invite = (invite_code or "").strip()
        if not normalized_invite or not invite_store.invite_is_valid(normalized_invite):
            retry_after = login_throttle.record_failure(ip_key)
            raise AuthServiceError(AuthErrorCode.INVITE_REQUIRED, retry_after=retry_after)

    status, user = account_store.create_account(
        username,
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
    token = session_store.create_session(user["id"])
    logger.info("新用户注册: %s (admin=%s)", username, bool(user.get("is_admin")))
    return AuthSession(token=token, user=user)


def login(username: str, password: str, client_ip: str) -> AuthSession:
    throttle_keys = [f"user:{username}", f"ip:{client_ip}"]
    locked = max((login_throttle.retry_after(key) for key in throttle_keys), default=0)
    if locked > 0:
        raise AuthServiceError(AuthErrorCode.LOGIN_THROTTLED, retry_after=locked)

    user = account_store.verify_credentials(username, password)
    if not user:
        retry_after = max(login_throttle.record_failure(key) for key in throttle_keys)
        raise AuthServiceError(AuthErrorCode.INVALID_CREDENTIALS, retry_after=retry_after)

    for key in throttle_keys:
        login_throttle.reset(key)
    return AuthSession(token=session_store.create_session(user["id"]), user=user)


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


def create_invite(admin_id: int, expires_in_days: int | None) -> dict:
    expires_at = invite_expiry(expires_in_days) if expires_in_days else None
    return invite_store.create_invite(
        admin_id,
        generate_invite_code(),
        expires_at=expires_at,
    )


def list_invites(admin_id: int) -> list[dict]:
    return invite_store.list_invites(admin_id)


def revoke_invite(code: str, admin_id: int) -> None:
    status = invite_store.revoke_invite(code, admin_id)
    if status == "not_found":
        raise AuthServiceError(AuthErrorCode.INVITE_NOT_FOUND)
    if status == "used":
        raise AuthServiceError(AuthErrorCode.INVITE_USED)


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
    return PasswordResetLink(
        username=target["username"],
        token=token,
        expires_at=expires_at,
    )


def reset_password(token: str, new_password: str, client_ip: str) -> None:
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
