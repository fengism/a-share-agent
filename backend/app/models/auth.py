"""Pydantic models for the auth API."""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    must_change_password: bool = False


class AuthResponse(BaseModel):
    token: str
    user: UserOut


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
    username: str
    # Hours until the reset link expires (default 24h, max 7 days).
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class ResetLinkOut(BaseModel):
    username: str
    token: str
    expires_at: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)
