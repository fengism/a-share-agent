"""LLM 配置的多用户继承语义：默认用管理员那套，自己配了就用自己配的。

规则（`app.configuration.effective.overlay_private`）：
1. 用户没有个人 LLM 配置 → 完全继承全局（管理员）配置；
2. 用户配了自己的 Key（端点不变）→ 用自己的 Key；
3. 用户把端点换成自己的服务（provider / base_url 变化）→ **不再附带管理员的 Key**，
   必须自备（这是凭据泄漏防护：否则管理员 Key 会被发到用户/第三方地址）；
4. 清空个人配置 → 回退到全局配置。
"""

from __future__ import annotations

import uuid

import pytest

from app.configuration import get_settings
from app.configuration.effective import inherited_private_keys, overlay_private
from app.infrastructure.llm.spec import LLMConfigurationError


def _global_base(**updates):
    base = get_settings()
    payload = {
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "llm_base_url": "https://api.openai.com/v1",
        "llm_api_key": "sk-admin-secret",
        "llm_api_mode": "openai",
        "llm_temperature": 0.3,
    }
    payload.update(updates)
    return base.model_copy(update=payload)


def test_user_without_overrides_inherits_admin_config() -> None:
    base = _global_base()
    merged = overlay_private(base, {})

    assert merged.llm_provider == "openai"
    assert merged.llm_base_url == "https://api.openai.com/v1"
    assert merged.llm_api_key == "sk-admin-secret"
    assert merged.llm_model == "gpt-4o"


def test_user_with_own_key_uses_own_key() -> None:
    base = _global_base()
    merged = overlay_private(base, {"llm_api_key": "sk-user-key"})

    assert merged.llm_api_key == "sk-user-key"
    # 其它维度仍继承管理员（模型、端点）
    assert merged.llm_base_url == "https://api.openai.com/v1"
    assert merged.llm_model == "gpt-4o"


def test_user_bringing_own_endpoint_does_not_receive_admin_key() -> None:
    base = _global_base()
    merged = overlay_private(base, {"llm_base_url": "http://my-ollama:11434/v1"})

    assert merged.llm_base_url == "http://my-ollama:11434/v1"
    # 管理员 Key 绝不能被发到用户指定的地址
    assert merged.llm_api_key == ""


def test_switching_provider_without_key_clears_inherited_key() -> None:
    base = _global_base()
    merged = overlay_private(base, {"llm_provider": "deepseek"})

    assert merged.llm_provider == "deepseek"
    assert merged.llm_api_key == ""


def test_custom_endpoint_with_own_key_is_allowed() -> None:
    base = _global_base()
    merged = overlay_private(
        base,
        {"llm_base_url": "https://my-gateway.example.com/v1", "llm_api_key": "sk-mine"},
    )

    assert merged.llm_base_url == "https://my-gateway.example.com/v1"
    assert merged.llm_api_key == "sk-mine"


def test_endpoint_comparison_ignores_trailing_slash_and_case() -> None:
    base = _global_base()
    merged = overlay_private(base, {"llm_base_url": "https://API.OpenAI.com/v1/"})

    # 同一个端点（只是写法不同）→ 仍可复用管理员 Key
    assert merged.llm_api_key == "sk-admin-secret"


def test_clearing_personal_key_falls_back_to_admin_key() -> None:
    base = _global_base()
    merged = overlay_private(base, {"llm_api_key": ""})
    assert merged.llm_api_key == "sk-admin-secret"


def test_masked_secret_is_not_treated_as_override() -> None:
    """前端回显的脱敏值不能被当成"用户自己的 Key"。"""
    base = _global_base()
    merged = overlay_private(base, {"llm_api_key": "sk-a***cret"})
    assert merged.llm_api_key == "sk-admin-secret"


@pytest.mark.parametrize(
    ("overrides", "inherited"),
    [
        ({}, True),
        ({"llm_api_key": ""}, True),
        ({"llm_api_key": "sk-own"}, False),
    ],
)
def test_inherited_private_keys_reports_llm_source(overrides: dict, inherited: bool) -> None:
    assert ("llm_api_key" in inherited_private_keys(overrides)) is inherited


def test_config_response_reports_inheritance_for_regular_user() -> None:
    """`GET /api/config` 对普通用户返回 inherited_keys，管理员为空。"""
    from fastapi.testclient import TestClient

    from app.api.auth.dependencies import get_current_user
    from app.infrastructure.persistence import account_store
    from app.main import app

    user = account_store.create_user(f"llm_{uuid.uuid4().hex[:8]}", "Password123!")
    admin = account_store.create_user(
        f"llm_admin_{uuid.uuid4().hex[:8]}", "Password123!", is_admin=True
    )

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            body = client.get("/api/config").json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert body["is_admin"] is False
    assert "llm_api_key" in body["inherited_keys"]
    assert "llm_provider" in body["inherited_keys"]

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        with TestClient(app) as client:
            admin_body = client.get("/api/config").json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert admin_body["is_admin"] is True
    assert admin_body["inherited_keys"] == []


# --- 显式清空个人覆盖（「改用管理员配置」） -----------------------------------


_LLM_KEYS = ("llm_provider", "llm_base_url", "llm_model", "llm_api_key")


@pytest.fixture()
def global_llm_config():
    """临时把全局基线设成管理员已配置 LLM 的状态，结束后只恢复这几个字段。

    只回滚被改动的字段：`update_settings` 会触发配置变更副作用，传全字段会显著拖慢用例。
    """
    from app import configuration

    original = {key: getattr(get_settings(), key) for key in _LLM_KEYS}
    configuration.update_settings(
        {
            "llm_provider": "openai",
            "llm_base_url": "https://api.openai.com/v1",
            "llm_model": "gpt-4o",
            "llm_api_key": "sk-admin-global",
        }
    )
    try:
        yield "sk-admin-global"
    finally:
        configuration.update_settings(original)


def test_explicit_empty_secret_deletes_personal_override(global_llm_config) -> None:
    """前端「改用管理员配置」传空串：删掉个人 Key 行，重新继承管理员配置。"""
    from app.infrastructure.persistence import account_store, user_config_store
    from app.modules.settings.service import get_user_settings, update_user_settings

    user = account_store.create_user(f"clear_{uuid.uuid4().hex[:8]}", "Password123!")
    update_user_settings(
        user["id"],
        False,
        {
            "llm_provider": "openai",
            "llm_base_url": "https://my-gw.example.com/v1",
            "llm_model": "gpt-4o",
            "llm_api_key": "sk-personal",
        },
    )
    assert user_config_store.get_user_config(user["id"])["llm_api_key"] == "sk-personal"

    # 与前端「改用管理员配置」提交的补丁一致：整组清空
    update_user_settings(
        user["id"],
        False,
        {
            "llm_provider": "",
            "llm_base_url": "",
            "llm_model": "",
            "llm_api_key": "",
            "llm_api_version": "",
            "llm_sub_model": "",
        },
    )

    rows = user_config_store.get_user_config(user["id"])
    assert "llm_api_key" not in rows, "个人 Key 必须被删除而不是留空串"
    leftover = sorted(key for key in rows if key.startswith("llm_"))
    assert leftover == [], f"个人 LLM 覆盖应整组删除，残留: {leftover}"

    effective = get_user_settings(user["id"])
    assert effective.llm_api_key == global_llm_config
    assert effective.llm_base_url == "https://api.openai.com/v1"


def test_masked_secret_does_not_delete_personal_override(global_llm_config) -> None:
    """前端回显的掩码值不能当成"清空"，否则一保存就把用户 Key 删了。"""
    from app.infrastructure.persistence import account_store, user_config_store
    from app.modules.settings.service import update_user_settings

    user = account_store.create_user(f"mask_{uuid.uuid4().hex[:8]}", "Password123!")
    update_user_settings(
        user["id"],
        False,
        {"llm_base_url": "https://custom.example.com/v1", "llm_api_key": "sk-personal"},
    )

    update_user_settings(user["id"], False, {"llm_api_key": "sk-p***onal"})

    assert user_config_store.get_user_config(user["id"])["llm_api_key"] == "sk-personal"


def test_config_api_accepts_clearing_personal_llm_key(global_llm_config) -> None:
    """PUT /api/config 携带空串 Key 时返回 200，且个人覆盖被清除。"""
    from fastapi.testclient import TestClient

    from app.api.auth.dependencies import get_current_user
    from app.infrastructure.persistence import account_store, user_config_store
    from app.main import app

    user = account_store.create_user(f"api_{uuid.uuid4().hex[:8]}", "Password123!")
    user_config_store.set_user_config(user["id"], {"llm_api_key": "sk-personal"})

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            response = client.put("/api/config", json={"llm_api_key": ""})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    assert "llm_api_key" not in user_config_store.get_user_config(user["id"])
    body = response.json()
    assert "llm_api_key" in body["inherited_keys"]


# --- 咽喉层：resolve_llm_client_spec 的全局 Key 回退 -------------------------------


def test_spec_does_not_leak_global_key_to_foreign_endpoint(global_llm_config) -> None:
    """即便上层漏了（存量数据/后台任务直接构造 settings），也不把管理员 Key 发到别的端点。"""
    from app.configuration import get_settings
    from app.infrastructure.llm.spec import resolve_llm_client_spec

    foreign = get_settings().model_copy(
        update={
            "llm_provider": "openai",
            "llm_base_url": "https://my-gw.example.com/v1",
            "llm_model": "gpt-4o",
            "llm_api_key": "",
        }
    )
    with pytest.raises(LLMConfigurationError):
        resolve_llm_client_spec(foreign)


def test_spec_reuses_global_key_on_same_endpoint(global_llm_config) -> None:
    from app.configuration import get_settings
    from app.infrastructure.llm.spec import resolve_llm_client_spec

    same = get_settings().model_copy(update={"llm_api_key": ""})
    assert resolve_llm_client_spec(same).api_key == global_llm_config

    # 同一端点的写法差异（大小写、尾斜杠）不应被当成"换了端点"
    variant = get_settings().model_copy(
        update={"llm_api_key": "", "llm_base_url": "https://API.OpenAI.com/v1/"}
    )
    assert resolve_llm_client_spec(variant).api_key == global_llm_config


def test_spec_uses_own_key_on_foreign_endpoint(global_llm_config) -> None:
    from app.configuration import get_settings
    from app.infrastructure.llm.spec import resolve_llm_client_spec

    own = get_settings().model_copy(
        update={"llm_base_url": "https://my-gw.example.com/v1", "llm_api_key": "sk-mine"}
    )
    spec = resolve_llm_client_spec(own)
    assert spec.api_key == "sk-mine"
    assert spec.base_url == "https://my-gw.example.com/v1"


def test_spec_allows_keyless_local_provider_on_foreign_endpoint(global_llm_config) -> None:
    """本地 Ollama 这类不需要 Key 的 provider 不该被拦住。"""
    from app.configuration import get_settings
    from app.infrastructure.llm.spec import resolve_llm_client_spec

    local = get_settings().model_copy(
        update={
            "llm_provider": "ollama",
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "qwen3:8b",
            "llm_api_key": "",
        }
    )
    assert resolve_llm_client_spec(local).api_key == "local"


def test_regular_user_cannot_only_set_key_without_url(global_llm_config) -> None:
    """普通用户不能只设置 Key 而不改 URL（端点与凭据必须成对）。"""
    from app.infrastructure.persistence import account_store
    from app.modules.settings.service import update_user_settings

    user = account_store.create_user(f"nokey_{uuid.uuid4().hex[:8]}", "Password123!")
    with pytest.raises(LLMConfigurationError, match="不能只设置 API Key"):
        update_user_settings(user["id"], False, {"llm_api_key": "sk-personal"})


def test_regular_user_cannot_only_set_url_without_key(global_llm_config) -> None:
    """普通用户不能只改 URL 而不设 Key。"""
    from app.infrastructure.persistence import account_store
    from app.modules.settings.service import update_user_settings

    user = account_store.create_user(f"nourl_{uuid.uuid4().hex[:8]}", "Password123!")
    with pytest.raises(LLMConfigurationError, match="不能只修改 Base URL"):
        update_user_settings(user["id"], False, {"llm_base_url": "https://custom.example.com/v1"})


def test_regular_user_can_update_model_and_temperature_without_url_and_key(global_llm_config) -> None:
    """不改 URL 和 Key 时，普通用户可自由修改模型和温度系数。"""
    from app.infrastructure.persistence import account_store
    from app.modules.settings.service import update_user_settings

    user = account_store.create_user(f"model_{uuid.uuid4().hex[:8]}", "Password123!")
    result = update_user_settings(
        user["id"],
        False,
        {"llm_model": "gpt-4o-mini", "llm_temperature": 0.5},
    )
    assert result.settings.llm_model == "gpt-4o-mini"
    assert result.settings.llm_temperature == 0.5
    # 仍继承管理员的端点与 Key
    assert result.settings.llm_base_url == "https://api.openai.com/v1"
    assert result.settings.llm_api_key == global_llm_config

