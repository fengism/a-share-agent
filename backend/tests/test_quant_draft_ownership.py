"""量化策略草稿的归属隔离（B：在线策略对普通用户开放）。

规则：
- 普通用户只能列出/读取/校验/删除**自己创建的**草稿（越权一律 404，不泄露存在性）；
- 草稿回测产生的回测任务归属发起人；
- 「发布到全局策略注册表」与「策略注册表状态」仍然只有管理员能做。
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.persistence import account_store
from app.modules.quant.persistence import drafts as draft_store


def _new_user(prefix: str = "draft") -> dict:
    return account_store.create_user(f"{prefix}_{uuid.uuid4().hex[:8]}", "Password123!")


def _valid_definition() -> dict:
    """取一个内置策略的合法定义，保证 `StrategyDefinition.model_validate` 通过。"""
    from app.modules.quant.strategies.registry import get_strategy_registry

    registry = get_strategy_registry()
    registry.ensure_loaded()
    definition = registry.descriptors()[0].definition
    return definition.model_dump(mode="json")


def _new_draft(owner: dict) -> str:
    row = draft_store.create_draft(
        created_by=int(owner["id"]),
        prompt="单元测试草稿",
        definition=_valid_definition(),
        definition_hash="sha256:" + "0" * 64,
        status="validated",
        validation=None,
    )
    return row.id


@pytest.fixture()
def as_user():
    from app.api.auth.dependencies import get_current_user
    from app.main import app

    def _apply(user: dict):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _apply
    app.dependency_overrides.pop(get_current_user, None)


async def _request(method: str, path: str, json_body: dict | None = None) -> tuple[int, dict]:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, path, json=json_body)
    payload = response.json() if response.content else {}
    return response.status_code, payload


async def test_list_only_returns_own_drafts(as_user) -> None:
    me = _new_user("mine")
    other = _new_user("other")
    my_draft = _new_draft(me)
    other_draft = _new_draft(other)

    as_user(me)
    status, payload = await _request("GET", "/api/quant/strategy-drafts")

    assert status == 200
    ids = {item["id"] for item in payload}
    assert my_draft in ids
    assert other_draft not in ids


async def test_get_other_users_draft_returns_404(as_user) -> None:
    me = _new_user("reader")
    other = _new_user("owner")
    foreign = _new_draft(other)

    as_user(me)
    status, payload = await _request("GET", f"/api/quant/strategy-drafts/{foreign}")

    assert status == 404
    assert payload["code"] == "quant.strategy_draft_not_found"


async def test_validate_and_delete_are_owner_scoped(as_user) -> None:
    me = _new_user("intruder")
    other = _new_user("victim")
    foreign = _new_draft(other)

    as_user(me)
    validate_status, _ = await _request("POST", f"/api/quant/strategy-drafts/{foreign}/validate")
    delete_status, delete_payload = await _request("DELETE", f"/api/quant/strategy-drafts/{foreign}")

    assert validate_status == 404
    assert delete_status == 404
    assert delete_payload["code"] == "quant.strategy_draft_not_found"
    # 草稿没有被误删
    assert draft_store.get_draft(foreign, created_by=int(other["id"])) is not None


async def test_owner_can_read_and_delete_own_draft(as_user) -> None:
    me = _new_user("owner")
    draft_id = _new_draft(me)

    as_user(me)
    read_status, payload = await _request("GET", f"/api/quant/strategy-drafts/{draft_id}")
    assert read_status == 200
    assert payload["id"] == draft_id

    delete_status, _ = await _request("DELETE", f"/api/quant/strategy-drafts/{draft_id}")
    assert delete_status == 200
    assert draft_store.get_draft(draft_id) is None


async def test_publish_still_admin_only(as_user) -> None:
    me = _new_user("publisher")
    draft_id = _new_draft(me)

    as_user(me)
    status, payload = await _request(
        "POST",
        f"/api/quant/strategy-drafts/{draft_id}/publish",
        {"expected_definition_hash": "sha256:" + "0" * 64},
    )

    assert status == 403
    assert payload["code"] == "auth.admin_required"


async def test_strategy_registry_status_still_admin_only(as_user) -> None:
    me = _new_user("registry")
    as_user(me)
    status, payload = await _request("GET", "/api/quant/strategy-registry")

    assert status == 403
    assert payload["code"] == "auth.admin_required"


async def test_admin_sees_all_drafts(as_user) -> None:
    admin = account_store.create_user(f"admin_{uuid.uuid4().hex[:8]}", "Password123!", is_admin=True)
    other = _new_user("someone")
    mine = _new_draft(admin)
    theirs = _new_draft(other)

    as_user(admin)
    status, payload = await _request("GET", "/api/quant/strategy-drafts")

    assert status == 200
    ids = {item["id"] for item in payload}
    assert {mine, theirs} <= ids


async def test_draft_routes_require_auth() -> None:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/quant/strategy-drafts")
    assert response.status_code == 401
