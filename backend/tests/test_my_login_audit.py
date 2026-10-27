"""普通用户自助查看自己的登录记录（A：`/auth/audit-logs/me`）。

安全边界：接口只按登录态里的 ``user_id`` 过滤，不接受任何客户端传入的用户标识，
因此既看不到别人的记录，也无法通过 `%`/`_` 之类的通配符放大查询范围。
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.persistence import account_store


def _new_user(prefix: str = "audit") -> dict:
    return account_store.create_user(f"{prefix}_{uuid.uuid4().hex[:8]}", "Password123!")


def _record(user: dict, status: str, ip: str = "203.0.113.5") -> None:
    account_store.record_login_audit(
        str(user["username"]),
        int(user["id"]),
        ip,
        "UnitTest/1.0",
        status,
    )


@pytest.fixture()
def as_user():
    """把 `get_current_user` 覆盖成指定用户（不经过真实 Cookie 流程）。"""
    from app.api.auth.dependencies import get_current_user
    from app.main import app

    def _apply(user: dict):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _apply
    app.dependency_overrides.pop(get_current_user, None)


async def _get(path: str) -> tuple[int, dict]:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    return response.status_code, response.json()


async def test_my_audit_logs_only_return_own_records(as_user) -> None:
    me = _new_user("self")
    other = _new_user("other")
    _record(me, "success", "198.51.100.1")
    _record(me, "failed_credentials", "198.51.100.2")
    _record(other, "success", "198.51.100.3")

    as_user(me)
    status, payload = await _get("/api/auth/audit-logs/me")

    assert status == 200
    ips = {item["ip_address"] for item in payload["items"]}
    assert ips == {"198.51.100.1", "198.51.100.2"}
    assert payload["total"] == 2
    assert all(item["user_id"] == me["id"] for item in payload["items"])


async def test_my_audit_logs_supports_status_filter(as_user) -> None:
    me = _new_user("filter")
    _record(me, "success", "198.51.100.10")
    _record(me, "failed_credentials", "198.51.100.11")

    as_user(me)
    status, payload = await _get("/api/auth/audit-logs/me?status=failed_credentials")

    assert status == 200
    assert payload["total"] == 1
    assert payload["items"][0]["status"] == "failed_credentials"


async def test_my_audit_logs_ignore_username_param(as_user) -> None:
    """即使传入别人的用户名，也只会返回自己的记录（参数不被采信）。"""
    me = _new_user("mine")
    other = _new_user("victim")
    _record(me, "success", "198.51.100.20")
    _record(other, "success", "198.51.100.21")

    as_user(me)
    status, payload = await _get(f"/api/auth/audit-logs/me?username={other['username']}")

    assert status == 200
    assert payload["total"] == 1
    assert payload["items"][0]["user_id"] == me["id"]


async def test_my_audit_logs_require_auth() -> None:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/auth/audit-logs/me")
    assert response.status_code == 401


async def test_admin_audit_logs_still_admin_only(as_user) -> None:
    """原有管理员全量接口不因新增自助接口而放宽。"""
    me = _new_user("plain")
    as_user(me)
    status, payload = await _get("/api/auth/admin/audit-logs")

    assert status == 403
    assert payload["code"] == "auth.admin_required"
