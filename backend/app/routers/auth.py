"""Account endpoints: register, login, logout, me, and admin invites.

Registration policy: the FIRST registered user automatically becomes admin;
every subsequent registration requires a valid, unused invite code created by
an admin.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db import user_store
from app.utils import login_throttle
from app.utils.auth import generate_invite_code, invite_expiry, now_ts, verify_password, hash_token
from app.models.auth import (
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
    AuthResponse,
    UserOut,
    InviteOut,
    CreateInviteRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_security = HTTPBearer(auto_error=False)


def _user_out(u: dict) -> UserOut:
    return UserOut(id=u["id"], username=u["username"], is_admin=bool(u["is_admin"]))


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> dict:
    """FastAPI dependency: resolve the authenticated user from the Bearer token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    user = user_store.get_user_by_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest) -> AuthResponse:
    if user_store.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")

    is_first = user_store.count_users() == 0
    invite_code: str | None = None
    if not is_first:
        invite_code = (req.invite_code or "").strip()
        if not invite_code or not user_store.invite_is_valid(invite_code):
            raise HTTPException(status_code=403, detail="需要有效的邀请码")

    # Create the user and consume the invite atomically. If the invite can't be
    # claimed (already used / expired / lost a race), the user insert is rolled
    # back — so a failed registration never leaves a usable orphan account.
    status, user = user_store.create_account(
        req.username, req.password, is_admin=is_first, invite_code=invite_code
    )
    if status == "duplicate":
        raise HTTPException(status_code=409, detail="用户名已存在")
    if user is None:
        raise HTTPException(status_code=403, detail="邀请码无效或已被使用")

    token = user_store.create_session(user["id"])
    logger.info("新用户注册: %s (admin=%s)", req.username, is_first)
    return AuthResponse(token=token, user=_user_out(user))


def _client_ip(request: Request) -> str:
    """Best-effort client IP, honouring X-Forwarded-For behind a proxy."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _throttle_keys(username: str, request: Request) -> list[str]:
    return [f"user:{username}", f"ip:{_client_ip(request)}"]


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request) -> AuthResponse:
    keys = _throttle_keys(req.username, request)

    # Reject early if this username or IP is currently locked out.
    locked = max((login_throttle.retry_after(k) for k in keys), default=0)
    if locked > 0:
        raise HTTPException(
            status_code=429,
            detail=f"尝试过于频繁，请 {locked} 秒后再试",
            headers={"Retry-After": str(locked)},
        )

    user = user_store.verify_credentials(req.username, req.password)
    if not user:
        after = max(login_throttle.record_failure(k) for k in keys)
        if after > 0:
            raise HTTPException(
                status_code=429,
                detail=f"失败次数过多，已临时锁定，请 {after} 秒后再试",
                headers={"Retry-After": str(after)},
            )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # Success clears the counters for this username + IP.
    for k in keys:
        login_throttle.reset(k)
    token = user_store.create_session(user["id"])
    return AuthResponse(token=token, user=_user_out(user))


@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> dict:
    if credentials is not None:
        user_store.delete_session(credentials.credentials)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    user: dict = Depends(get_current_user),
) -> dict:
    """Change the current user's password after verifying the old one, then
    revoke every other session (the current device stays logged in)."""
    if not verify_password(req.old_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="原密码错误")
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    user_store.update_password(user["id"], req.new_password)
    keep = hash_token(credentials.credentials) if credentials else None
    revoked = user_store.delete_other_sessions(user["id"], keep)
    logger.info("用户修改密码: id=%s, 其它会话已吊销=%s", user["id"], revoked)
    return {"ok": True, "revoked_sessions": revoked}


@router.get("/needs-setup")
def needs_setup() -> dict:
    """Whether the instance has no users yet (first registration becomes admin)."""
    return {"needs_setup": user_store.count_users() == 0}


def _invite_out(inv: dict) -> InviteOut:
    used = inv["used_by"] is not None
    expires_at = inv.get("expires_at")
    expired = (not used) and bool(expires_at) and expires_at < now_ts()
    return InviteOut(
        code=inv["code"],
        used=used,
        expired=expired,
        created_at=inv.get("created_at"),
        expires_at=expires_at,
    )


@router.post("/invite", response_model=InviteOut)
def create_invite(
    req: CreateInviteRequest | None = None,
    admin: dict = Depends(require_admin),
) -> InviteOut:
    expires_at = invite_expiry(req.expires_in_days) if req and req.expires_in_days else None
    inv = user_store.create_invite(admin["id"], generate_invite_code(), expires_at=expires_at)
    return _invite_out(inv)


@router.get("/invites", response_model=list[InviteOut])
def list_invites(admin: dict = Depends(require_admin)) -> list[InviteOut]:
    return [_invite_out(i) for i in user_store.list_invites(admin["id"])]


@router.delete("/invite/{code}")
def revoke_invite(code: str, admin: dict = Depends(require_admin)) -> dict:
    """Cancel an unused invite. Already-used invites cannot be revoked."""
    status = user_store.revoke_invite(code, admin["id"])
    if status == "not_found":
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if status == "used":
        raise HTTPException(status_code=409, detail="该邀请码已被使用，无法撤销")
    return {"ok": True}
