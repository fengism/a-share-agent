from pydantic import BaseModel, Field, field_validator

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"


def validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("密码长度至少为 8 位")
    if len(v) > 128:
        raise ValueError("密码长度不能超过 128 位")
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("密码必须同时包含字母和数字")
    return v


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str | None = Field(default=None, max_length=256)

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_strength(v)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool = True
    must_change_password: bool = False
    created_at: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class OkResponse(BaseModel):
    ok: bool = True


class ChangePasswordResponse(OkResponse):
    revoked_sessions: int


class NeedsSetupResponse(BaseModel):
    needs_setup: bool


class CreateInviteRequest(BaseModel):
    # Days until the invite expires; omit / null = never expires.
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class InviteOut(BaseModel):
    code: str
    used: bool
    expired: bool = False
    created_at: str | None = None
    expires_at: str | None = None


class AdminResetLinkRequest(BaseModel):
    username: str = Field(max_length=32)
    # Hours until the reset link expires (default 24h, max 7 days).
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class ResetLinkOut(BaseModel):
    username: str
    token: str
    expires_at: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(max_length=256)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_strength(v)


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class UpdateUserRoleRequest(BaseModel):
    is_admin: bool


class RevokeSessionsResponse(OkResponse):
    revoked_sessions: int


class UpdateMustChangePasswordRequest(BaseModel):
    must_change_password: bool


class LoginAuditLogItem(BaseModel):
    id: int
    username: str
    user_id: int | None = None
    ip_address: str
    user_agent: str
    status: str
    details: str
    created_at: str


class LoginAuditLogsResponse(BaseModel):
    items: list[LoginAuditLogItem]
    total: int
    limit: int
    offset: int


class CleanupInvitesResponse(OkResponse):
    cleaned_count: int
