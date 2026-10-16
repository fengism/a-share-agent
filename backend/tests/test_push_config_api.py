"""推送通道与 fuyao 凭证必须能通过配置接口读写。

回归背景：多通道推送（飞书/钉钉/企微/WxPusher）与 fuyao 曾在 Settings 中定义、
前端也有 UI，但未登记进 ``ConfigUpdateRequest``/``ConfigResponse``，导致
``PUT /config`` 静默丢弃、``GET /config`` 不返回。本测试固定住修复结果。
"""

from __future__ import annotations

import pytest

from app import configuration
from app.configuration import (
    GLOBAL_SYNCED_KEYS,
    PERSISTED_GLOBAL_KEYS,
    PRIVATE_USER_KEYS,
    SECRET_KEYS,
    Settings,
    get_settings,
)
from app.configuration.effective import overlay_private
from app.modules.settings import service
from app.modules.settings.schemas import ConfigResponse, ConfigUpdateRequest

PUSH_PATCH = {
    "push_auto_enabled": True,
    "push_daily_review_auto": True,
    "push_potential_auto": False,
    "push_feishu_enabled": True,
    "feishu_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
    "feishu_webhook_secret": "feishu-secret",
    "push_dingtalk_enabled": True,
    "dingtalk_webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=abc",
    "dingtalk_webhook_secret": "SECabc",
    "push_wecom_enabled": False,
    "wecom_webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
    "push_wxpusher_enabled": True,
    "wxpusher_app_token": "AT_abc",
    "wxpusher_uids": "UID_1,UID_2",
}

PUSH_KEYS = frozenset(PUSH_PATCH)


class _MemoryStore:
    def __init__(self) -> None:
        self.items: dict = {}

    def set(self, items: dict) -> None:
        self.items.update(items)

    def get(self) -> dict:
        return dict(self.items)


@pytest.fixture()
def memory_stores(monkeypatch: pytest.MonkeyPatch):
    user_store = _MemoryStore()
    global_store = _MemoryStore()
    monkeypatch.setattr(service.user_config_store, "set_user_config", lambda uid, items: user_store.set(items))
    monkeypatch.setattr(service.user_config_store, "get_user_config", lambda uid: user_store.get())
    monkeypatch.setattr(service.global_config_store, "set_global_config", global_store.set)
    original = get_settings()
    yield user_store, global_store
    configuration.update_settings(
        {name: getattr(original, name) for name in Settings.model_fields}
    )


def test_push_fields_are_registered_in_api_contract() -> None:
    for key in PUSH_KEYS:
        assert key in PRIVATE_USER_KEYS, f"{key} 应为用户私有配置"
        assert key in GLOBAL_SYNCED_KEYS, f"{key} 需同步到全局基线供后台推送使用"
        assert key in ConfigUpdateRequest.model_fields
        assert key in ConfigResponse.model_fields
    # 钉钉此前连白名单都缺失，这里单独固定
    assert "dingtalk_webhook_url" in PERSISTED_GLOBAL_KEYS or "dingtalk_webhook_url" in PRIVATE_USER_KEYS
    assert "dingtalk_webhook_secret" in SECRET_KEYS
    assert "fuyao_api_key" in SECRET_KEYS
    assert "fuyao_api_key" in PERSISTED_GLOBAL_KEYS
    assert "fuyao_api_key" in ConfigResponse.model_fields


def test_update_request_keeps_push_payload() -> None:
    payload = ConfigUpdateRequest(**PUSH_PATCH).model_dump(exclude_none=True)
    assert payload == PUSH_PATCH


def test_overlay_private_applies_push_values() -> None:
    effective = overlay_private(Settings(), PUSH_PATCH)
    for key, value in PUSH_PATCH.items():
        assert getattr(effective, key) == value


def test_non_admin_push_config_stays_private(memory_stores) -> None:
    user_store, global_store = memory_stores
    result = service.update_user_settings(7, False, dict(PUSH_PATCH))

    assert user_store.items == PUSH_PATCH
    assert global_store.items == {}
    assert result.global_settings is None
    assert result.settings.push_auto_enabled is True
    assert result.settings.dingtalk_webhook_url == PUSH_PATCH["dingtalk_webhook_url"]


def test_admin_push_config_syncs_to_global_baseline(memory_stores) -> None:
    user_store, global_store = memory_stores
    result = service.update_user_settings(1, True, dict(PUSH_PATCH))

    assert user_store.items == PUSH_PATCH
    # 管理员保存后同步全局，保证无用户上下文的后台收盘推送可用
    assert global_store.items == PUSH_PATCH
    assert result.global_settings is not None
    assert result.global_settings.push_auto_enabled is True
    assert get_settings().dingtalk_webhook_secret == PUSH_PATCH["dingtalk_webhook_secret"]


def test_fuyao_key_is_admin_only(memory_stores) -> None:
    with pytest.raises(service.GlobalSettingsPermissionError):
        service.update_user_settings(7, False, {"fuyao_api_key": "k"})
    service.update_user_settings(1, True, {"fuyao_api_key": "k"})
    assert get_settings().fuyao_api_key == "k"


def test_unknown_field_is_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConfigUpdateRequest(not_a_real_setting=1)
