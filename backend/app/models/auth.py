"""Pydantic models for the auth API."""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool


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
