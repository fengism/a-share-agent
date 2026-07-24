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


class InviteOut(BaseModel):
    code: str
    used: bool
    created_at: str | None = None
    expires_at: str | None = None
