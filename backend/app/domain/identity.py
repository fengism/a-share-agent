"""认证流程跨层共享的身份模型。"""

from typing_extensions import NotRequired, TypedDict


class AuthenticatedUser(TypedDict):
    id: int
    username: str
    is_admin: bool | int
    is_active: NotRequired[bool | int]
    must_change_password: NotRequired[bool | int]
    created_at: NotRequired[str]


class UserRecord(AuthenticatedUser):
    password_hash: str
    created_at: NotRequired[str]


class LoginAuditRecord(TypedDict):
    id: int
    username: str
    user_id: int | None
    ip_address: str
    user_agent: str
    status: str
    details: str
    created_at: str
