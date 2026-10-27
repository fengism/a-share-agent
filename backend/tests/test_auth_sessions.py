"""登录设备自助管理（/auth/sessions）测试。"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_token
from app.infrastructure.persistence import account_store, session_store
from app.modules.auth import service as auth_service


def _handle(token: str) -> str:
    """对外暴露的会话句柄 = token 哈希前缀（明文 token 绝不外泄）。"""
    return hash_token(token)[: session_store.SESSION_HANDLE_LENGTH]


def _new_user(prefix: str = "sess") -> dict:
    return account_store.create_user(f"{prefix}_{uuid.uuid4().hex[:8]}", "Password123!")


def test_create_session_records_origin() -> None:
    user = _new_user()
    token = session_store.create_session(user["id"], ip_address="198.51.100.7", user_agent="UnitTest/1.0")

    sessions = session_store.list_user_sessions(user["id"], current_token=token)
    assert len(sessions) == 1
    record = sessions[0]
    assert record["ip_address"] == "198.51.100.7"
    assert record["user_agent"] == "UnitTest/1.0"
    assert record["is_current"] is True
    # 句柄是 token 哈希前缀，绝不等于明文 token
    assert record["session_id"] == _handle(token)
    assert record["session_id"] != token
    assert len(str(record["session_id"])) == session_store.SESSION_HANDLE_LENGTH
    assert record["created_at"] and record["expires_at"]


def test_list_sessions_marks_only_current_and_hides_other_users() -> None:
    user = _new_user()
    other = _new_user("other")
    first = session_store.create_session(user["id"], ip_address="10.0.0.1", user_agent="A")
    second = session_store.create_session(user["id"], ip_address="10.0.0.2", user_agent="B")
    session_store.create_session(other["id"], ip_address="10.0.0.3", user_agent="C")

    sessions = session_store.list_user_sessions(user["id"], current_token=first)
    assert len(sessions) == 2
    current = [item for item in sessions if item["is_current"]]
    assert len(current) == 1
    assert current[0]["ip_address"] == "10.0.0.1"
    assert {item["session_id"] for item in sessions} == {_handle(first), _handle(second)}


def test_revoke_session_is_scoped_to_owner() -> None:
    owner = _new_user("owner")
    intruder = _new_user("intruder")
    token = session_store.create_session(owner["id"], ip_address="10.0.0.9", user_agent="A")
    handle = _handle(token)

    # 别人拿到句柄也删不掉
    assert session_store.revoke_user_session(intruder["id"], handle) is False
    assert len(session_store.list_user_sessions(owner["id"])) == 1

    assert session_store.revoke_user_session(owner["id"], handle) is True
    assert session_store.list_user_sessions(owner["id"]) == []
    # 会话令牌随之失效
    assert session_store.get_user_by_token(token) is None


@pytest.mark.parametrize("bad_handle", ["", "   ", "abc", "zzzzzzzzzzzz", "../etc/passwd", "%"])
def test_revoke_session_rejects_invalid_handles(bad_handle: str) -> None:
    user = _new_user("badhandle")
    session_store.create_session(user["id"])
    assert session_store.revoke_user_session(user["id"], bad_handle) is False
    assert len(session_store.list_user_sessions(user["id"])) == 1


def test_revoke_own_session_writes_audit_record() -> None:
    from app.infrastructure.persistence import admin_audit_store

    user = _new_user("selfrevoke")
    token = session_store.create_session(user["id"], ip_address="10.0.0.11", user_agent="A")
    handle = _handle(token)

    assert auth_service.revoke_own_session(user, handle, current_token=None) is True
    items, _ = admin_audit_store.list_admin_actions(action="session.revoke", actor_username="")
    mine = [item for item in items if item["target_label"] == user["username"]]
    assert len(mine) == 1
    assert '"self": true' in mine[0]["details"]
    assert mine[0]["target_id"] == str(user["id"])


async def test_sessions_api_lists_and_revokes_own_sessions() -> None:
    from app.api.auth.dependencies import get_current_user
    from app.main import app

    user = _new_user("api")
    keep = session_store.create_session(user["id"], ip_address="10.1.1.1", user_agent="Keep/1.0")
    drop = session_store.create_session(user["id"], ip_address="10.1.1.2", user_agent="Drop/1.0")
    drop_handle = _handle(drop)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get("/api/auth/sessions")
            assert listed.status_code == 200
            payload = listed.json()["items"]
            assert len(payload) == 2
            assert any(item["ip_address"] == "10.1.1.2" for item in payload)

            removed = await client.delete(f"/api/auth/sessions/{drop_handle}")
            assert removed.status_code == 200
            assert removed.json()["ok"] is True

            # 同一个句柄再删一次 → 404
            again = await client.delete(f"/api/auth/sessions/{drop_handle}")
            assert again.status_code == 404
            assert again.json()["code"] == "auth.session_not_found"

            remaining = await client.get("/api/auth/sessions")
            assert len(remaining.json()["items"]) == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert session_store.get_user_by_token(keep) is not None
    assert session_store.get_user_by_token(drop) is None


async def test_sessions_api_requires_auth() -> None:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/auth/sessions")
    assert resp.status_code == 401


# --- 密码强度策略（P5） -------------------------------------------------------


def test_register_rejects_weak_password() -> None:
    from app.modules.auth.service import AuthErrorCode, AuthServiceError

    with pytest.raises(AuthServiceError) as wrong:
        auth_service.register_account("weakuser", "password", None, "127.0.0.1")
    assert wrong.value.code == AuthErrorCode.WEAK_PASSWORD
    assert "常见" in wrong.value.reason


def test_register_rejects_password_containing_username() -> None:
    from app.modules.auth.service import AuthErrorCode, AuthServiceError

    with pytest.raises(AuthServiceError) as wrong:
        auth_service.register_account("traderjoe", "traderjoe-2026", None, "127.0.0.1")
    assert wrong.value.code == AuthErrorCode.WEAK_PASSWORD
    assert "用户名" in wrong.value.reason


def test_change_password_rejects_weak_new_password() -> None:
    from app.modules.auth.service import AuthErrorCode, AuthServiceError

    user = account_store.create_user(f"pwchg_{uuid.uuid4().hex[:8]}", "Password123!")
    with pytest.raises(AuthServiceError) as wrong:
        auth_service.change_password(user, "Password123!", "aaaaaaaa", None)
    assert wrong.value.code == AuthErrorCode.WEAK_PASSWORD


def test_reset_password_rejects_short_password() -> None:
    from app.modules.auth.service import AuthErrorCode, AuthServiceError

    with pytest.raises(AuthServiceError) as wrong:
        auth_service.reset_password("bogus-token", "short", "127.0.0.1")
    assert wrong.value.code == AuthErrorCode.WEAK_PASSWORD


@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("Password123!", True),
        ("Str0ng-Enough-2026", True),
        ("password", False),
        ("12345678", False),
        ("aaaaaaaa", False),
        ("short7!", False),
    ],
)
def test_password_policy_matrix(password: str, ok: bool) -> None:
    from app.core.security import WeakPasswordError, validate_password_policy

    if ok:
        validate_password_policy(password, "someoneelse")
    else:
        with pytest.raises(WeakPasswordError):
            validate_password_policy(password, "someoneelse")


def test_sessions_capped_per_user() -> None:
    """单用户会话数超过上限时淘汰最久未活跃的（P8）。"""
    from app.infrastructure.persistence import session_store

    user = account_store.create_user(f"cap_{uuid.uuid4().hex[:8]}", "Password123!")
    limit = session_store.MAX_SESSIONS_PER_USER
    tokens = [session_store.create_session(user["id"], ip_address="127.0.0.1") for _ in range(limit + 3)]

    sessions = session_store.list_user_sessions(user["id"], current_token=tokens[-1])
    assert len(sessions) == limit
    handles = {str(item["session_id"]) for item in sessions}
    # 最新的仍在列表里，最旧的 3 个被淘汰
    assert hash_token(tokens[-1])[: session_store.SESSION_HANDLE_LENGTH] in handles
    for stale in tokens[:3]:
        assert hash_token(stale)[: session_store.SESSION_HANDLE_LENGTH] not in handles
