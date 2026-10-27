"""管理员操作审计（admin_audit_logs）与审计保留期测试。"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.core.audit import current_audit_actor
from app.core.request_context import (
    reset_current_user,
    reset_request_origin,
    set_current_user,
    set_request_origin,
)
from app.domain.audit import AuditActor
from app.domain.timezones import market_now
from app.infrastructure.persistence import account_store, admin_audit_store
from app.modules.auth import service as auth_service


@pytest.fixture(autouse=True)
def _clean_audit_tables():
    """每个用例前清空两张审计表：断言可以用精确计数（同库跨用例累积会互相干扰）。"""
    from app.infrastructure.persistence.connection import get_connection, unit_of_work

    with unit_of_work(connection=get_connection("user"), immediate=True) as work:
        work.connection.execute("DELETE FROM admin_audit_logs")
        work.connection.execute("DELETE FROM login_audit_logs")
    yield


@pytest.fixture()
def admin_account(monkeypatch: pytest.MonkeyPatch):
    """创建管理员并把它绑定为当前请求的操作者（含 IP/UA）。"""
    suffix = uuid.uuid4().hex[:8]
    record = account_store.create_user(f"audit_admin_{suffix}", "Password123!", is_admin=True)
    origin_tokens = set_request_origin("203.0.113.7", "pytest-agent/1.0")
    user_token = set_current_user(record)
    monkeypatch.setattr(
        "app.infrastructure.persistence.admin_audit_store.current_audit_actor",
        lambda: AuditActor(
            user_id=record["id"],
            username=record["username"],
            ip_address="203.0.113.7",
            user_agent="pytest-agent/1.0",
        ),
    )
    try:
        yield record
    finally:
        reset_current_user(user_token)
        reset_request_origin(origin_tokens)


def test_record_and_list_admin_action(admin_account) -> None:
    admin_audit_store.record_admin_action(
        action="user.role",
        target_type="user",
        target_id=42,
        target_label="target_user",
        details={"is_admin": True},
    )
    items, total = admin_audit_store.list_admin_actions(action="user.role")
    assert total == 1
    assert items[0]["action"] == "user.role"
    assert items[0]["target_id"] == "42"
    assert items[0]["target_label"] == "target_user"
    assert items[0]["actor_id"] == admin_account["id"]
    assert items[0]["actor_ip"] == "203.0.113.7"
    assert '"is_admin": true' in items[0]["details"]


def test_record_admin_action_never_fails_business(monkeypatch: pytest.MonkeyPatch) -> None:
    """审计表不可用时应只记日志，不影响调用方。"""

    def boom(**kwargs):
        raise RuntimeError("db broken")

    monkeypatch.setattr(admin_audit_store, "unit_of_work", boom)
    admin_audit_store.record_admin_action(action="user.role", target_id=1)


def test_role_and_status_changes_are_audited(admin_account) -> None:
    other = account_store.create_user(f"audit_target_{uuid.uuid4().hex[:8]}", "Password123!")

    auth_service.update_user_role(admin_account["id"], other["id"], True)
    auth_service.update_user_status(admin_account["id"], other["id"], False)

    items, _ = admin_audit_store.list_admin_actions()
    actions = [item["action"] for item in items]
    assert actions[0] == "user.status"
    assert "user.role" in actions
    role_item = next(item for item in items if item["action"] == "user.role")
    assert role_item["actor_username"] == admin_account["username"]
    assert role_item["target_label"] == other["username"]
    assert '"is_admin": true' in role_item["details"]
    assert admin_audit_store.list_admin_actions(actor_username=admin_account["username"])[1] >= 2


def test_delete_user_is_audited(admin_account) -> None:
    victim = account_store.create_user(f"audit_victim_{uuid.uuid4().hex[:8]}", "Password123!")
    auth_service.delete_user(admin_account["id"], victim["id"])

    items, _ = admin_audit_store.list_admin_actions(action="user.delete")
    assert len(items) == 1
    assert items[0]["target_label"] == victim["username"]


def test_invite_lifecycle_is_audited(admin_account) -> None:
    invite = auth_service.create_invite(admin_account["id"], 3)
    auth_service.revoke_invite(invite["code"])
    auth_service.cleanup_expired_invites()

    actions = [item["action"] for item in admin_audit_store.list_admin_actions()[0]]
    assert actions[0] == "invite.cleanup"
    assert {"invite.create", "invite.revoke"} <= set(actions)


def test_global_config_change_audit_records_field_names_only() -> None:
    """全局配置审计只记录字段名，不得落密钥取值。"""
    import asyncio

    from app.modules.settings.service import SettingsUpdateResult

    audit_calls: list[dict] = []

    def fake_update(*args, **kwargs):
        patch = args[2]
        return SettingsUpdateResult(
            settings=object(),
            global_settings=object(),
            global_patch=dict(patch),
        )

    def fake_record(**kwargs):
        audit_calls.append(kwargs)

    from app.modules.settings import application as settings_application

    original_update = settings_application.update_user_settings
    original_record = settings_application.admin_audit_store.record_admin_action
    settings_application.update_user_settings = fake_update
    settings_application.admin_audit_store.record_admin_action = fake_record
    settings_application.apply_update_side_effects = lambda *a, **k: None
    try:
        asyncio.run(
            settings_application.save_user_settings(
                1,
                is_admin=True,
                patch={"llm_api_key": "sk-secret-value", "llm_provider": "openai"},
            )
        )
    finally:
        settings_application.update_user_settings = original_update
        settings_application.admin_audit_store.record_admin_action = original_record

    assert len(audit_calls) == 1
    call = audit_calls[0]
    assert call["action"] == "config.update_global"
    assert call["details"] == {"fields": ["llm_api_key", "llm_provider"]}
    assert "sk-secret-value" not in str(call)


def test_admin_audit_retention_purges_old_rows(admin_account) -> None:
    admin_audit_store.record_admin_action(action="user.role", target_id=1)
    # 手工插入一条 3 年前的记录
    old_created_at = (market_now() - timedelta(days=1100)).strftime("%Y-%m-%d %H:%M:%S")
    from app.infrastructure.persistence.connection import get_connection, unit_of_work

    with unit_of_work(connection=get_connection("user"), immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO admin_audit_logs (action, created_at)
            VALUES ('user.delete', ?)
            """,
            (old_created_at,),
        )

    assert admin_audit_store.list_admin_actions()[1] == 2
    assert admin_audit_store.purge_admin_actions(365) == 1
    items, total = admin_audit_store.list_admin_actions()
    assert total == 1
    assert items[0]["action"] == "user.role"
    # retention_days <= 0 表示永久保留
    assert admin_audit_store.purge_admin_actions(0) == 0


def test_login_audit_retention_purges_old_rows() -> None:
    account_store.record_login_audit("someone", None, "198.51.100.9", "ua", "failed_credentials")
    from app.infrastructure.persistence.connection import get_connection, unit_of_work

    with unit_of_work(connection=get_connection("user"), immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO login_audit_logs (username, status, created_at)
            VALUES ('old_scanner', 'failed_credentials', ?)
            """,
            ((market_now() - timedelta(days=900)).strftime("%Y-%m-%d %H:%M:%S"),),
        )

    assert account_store.purge_login_audit_logs(180) >= 1
    assert account_store.purge_login_audit_logs(0) == 0
    remaining, _ = account_store.list_login_audit_logs(
        limit=50, offset=0, username="old_scanner"
    )
    assert remaining == []


def test_purge_expired_auth_data_reports_audit_buckets() -> None:
    from app.runtime.maintenance import purge_expired_auth_data

    admin_audit_store.record_admin_action(action="invite.cleanup", details={"deleted": 0})
    result = purge_expired_auth_data(login_audit_retention_days=180, admin_audit_retention_days=365)
    assert "login_audit_logs" in result
    assert result["admin_audit_logs"] == 0
    assert "auth_sessions" in result


def test_current_audit_actor_reads_request_context() -> None:
    """操作者来自请求上下文（无请求时为匿名），业务层无需透传 Request。"""
    user = account_store.create_user(f"audit_ctx_{uuid.uuid4().hex[:8]}", "Password123!")
    anonymous = current_audit_actor()
    assert anonymous.user_id is None and anonymous.is_anonymous

    origin = set_request_origin("192.0.2.10", "ctx-agent/2.0")
    user_token = set_current_user(user)
    try:
        actor = current_audit_actor()
        assert actor.user_id == user["id"]
        assert actor.username == user["username"]
        assert actor.ip_address == "192.0.2.10"
        assert actor.user_agent == "ctx-agent/2.0"
        assert actor.is_anonymous is False
        assert actor.as_dict()["username"] == user["username"]
    finally:
        reset_current_user(user_token)
        reset_request_origin(origin)
