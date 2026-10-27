"""空库首用户注册的部署口令保护（P6）。

空库时第一个注册者会直接成为管理员。若实例在注册前已可被公网访问，
``ADMIN_SETUP_TOKEN`` 可以把这次注册锁在运维手里；未配置时保持旧行为。
"""

from __future__ import annotations

import uuid

import pytest

from app.configuration import get_settings
from app.modules.auth.service import AuthErrorCode, AuthServiceError


@pytest.fixture()
def bootstrap_open(monkeypatch: pytest.MonkeyPatch):
    """把实例伪装成"空库首次注册"：count_users()==0 且 create_account 直接建管理员。

    测试库是共享的，直接清空 users 会污染其他用例；这里只影响被测流程。
    """
    from app.infrastructure.persistence import account_store

    def fake_create_account(username, password, *, is_admin, invite_code):
        user = account_store.create_user(username, password, is_admin=is_admin)
        return ("created", user)

    monkeypatch.setattr(account_store, "count_users", lambda: 0)
    monkeypatch.setattr(account_store, "create_account", fake_create_account)
    yield


@pytest.fixture()
def setup_token_env(monkeypatch: pytest.MonkeyPatch, bootstrap_open):
    """配置 ADMIN_SETUP_TOKEN，并把用户表清空以进入 needs-setup 状态。"""
    monkeypatch.setattr(get_settings(), "admin_setup_token", "S3cret-Setup-Token", raising=False)
    yield "S3cret-Setup-Token"


def _register(username: str, setup_token: str | None):
    from app.modules.auth import service

    return service.register_account(
        username,
        "Password123!",
        None,
        "127.0.0.1",
        setup_token=setup_token,
    )


def test_first_registration_requires_setup_token_when_configured(setup_token_env) -> None:
    with pytest.raises(AuthServiceError) as error:
        _register(f"admin_{uuid.uuid4().hex[:6]}", None)
    assert error.value.code == AuthErrorCode.SETUP_TOKEN_INVALID


def test_first_registration_rejects_wrong_setup_token(setup_token_env) -> None:
    with pytest.raises(AuthServiceError) as error:
        _register(f"admin_{uuid.uuid4().hex[:6]}", "not-the-token")
    assert error.value.code == AuthErrorCode.SETUP_TOKEN_INVALID


def test_first_registration_succeeds_with_setup_token(setup_token_env) -> None:
    session = _register(f"admin_{uuid.uuid4().hex[:6]}", setup_token_env)
    assert bool(session.user["is_admin"]) is True


def test_setup_token_not_required_when_unset(
    monkeypatch: pytest.MonkeyPatch, bootstrap_open
) -> None:
    monkeypatch.setattr(get_settings(), "admin_setup_token", "", raising=False)
    session = _register(f"admin_{uuid.uuid4().hex[:6]}", None)
    assert bool(session.user["is_admin"]) is True


def test_requires_setup_token_reflects_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.auth import service

    monkeypatch.setattr(get_settings(), "admin_setup_token", "", raising=False)
    assert service.requires_setup_token() is False
    monkeypatch.setattr(get_settings(), "admin_setup_token", "abc", raising=False)
    assert service.requires_setup_token() is True


def test_needs_setup_endpoint_exposes_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import auth as auth_routes
    from app.modules.auth import service

    monkeypatch.setattr(auth_routes.auth_service, "needs_setup", lambda: True)
    monkeypatch.setattr(auth_routes.auth_service, "requires_setup_token", lambda: True)
    assert service  # 保持导入，避免 lint 未使用告警

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/api/auth")
    with TestClient(app) as client:
        payload = client.get("/api/auth/needs-setup").json()
    assert payload == {"needs_setup": True, "requires_setup_token": True}
