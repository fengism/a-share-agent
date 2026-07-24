"""Account endpoints: register, login, logout, me, and admin invites.

Registration policy: the FIRST registered user automatically becomes admin;
every subsequent registration requires a valid, unused invite code created by
an admin.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db import user_store
from app.utils.auth import generate_invite_code
from app.models.auth import RegisterRequest, LoginRequest, AuthResponse, UserOut, InviteOut

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
    if not is_first and not (req.invite_code and user_store.invite_is_valid(req.invite_code)):
        raise HTTPException(status_code=403, detail="需要有效的邀请码")

    user = user_store.create_user(req.username, req.password, is_admin=is_first)

    if not is_first and not user_store.consume_invite(req.invite_code, user["id"]):
        # Lost a race for the invite — reject to avoid a free account.
        raise HTTPException(status_code=403, detail="邀请码无效或已被使用")

    token = user_store.create_session(user["id"])
    logger.info("新用户注册: %s (admin=%s)", req.username, is_first)
    return AuthResponse(token=token, user=_user_out(user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    user = user_store.verify_credentials(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
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


@router.get("/needs-setup")
def needs_setup() -> dict:
    """Whether the instance has no users yet (first registration becomes admin)."""
    return {"needs_setup": user_store.count_users() == 0}


def _invite_out(inv: dict) -> InviteOut:
    return InviteOut(
        code=inv["code"],
        used=inv["used_by"] is not None,
        created_at=inv.get("created_at"),
        expires_at=inv.get("expires_at"),
    )


@router.post("/invite", response_model=InviteOut)
def create_invite(admin: dict = Depends(require_admin)) -> InviteOut:
    inv = user_store.create_invite(admin["id"], generate_invite_code())
    return _invite_out(inv)


@router.get("/invites", response_model=list[InviteOut])
def list_invites(admin: dict = Depends(require_admin)) -> list[InviteOut]:
    return [_invite_out(i) for i in user_store.list_invites(admin["id"])]
