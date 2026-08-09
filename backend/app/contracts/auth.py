"""认证流程跨层共享的数据契约。"""

from typing_extensions import NotRequired, TypedDict


class AuthenticatedUser(TypedDict):
    id: int
    username: str
    is_admin: bool | int
    must_change_password: NotRequired[bool | int]


class UserRecord(AuthenticatedUser):
    password_hash: str
    created_at: NotRequired[str]
