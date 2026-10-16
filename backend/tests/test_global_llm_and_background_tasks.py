"""全局大模型配置与后台常驻任务开关测试。

1. 常驻后台任务默认关闭，支持持久化更新与热生效。
2. 用户未配置个人 API Key 时，自动回退使用全局 Key。
3. 管理员保存大模型配置时，自动同步至全局基线配置。
"""

from __future__ import annotations

from app.configuration import GLOBAL_LLM_KEYS, PERSISTED_GLOBAL_KEYS, Settings, get_settings
from app.configuration.effective import overlay_private
from app.infrastructure.llm.spec import resolve_llm_client_spec
from app.modules.settings.schemas import ConfigResponse, ConfigUpdateRequest


def test_background_task_switches_are_persisted_global_settings() -> None:
    expected_switches = {
        "macro_analysis_prewarm_enabled",
        "daily_review_prewarm_enabled",
        "potential_stock_daily_enabled",
        "stock_valuation_snapshot_refresh_enabled",
    }
    for key in expected_switches:
        assert key in PERSISTED_GLOBAL_KEYS
        assert key in ConfigUpdateRequest.model_fields
        assert key in ConfigResponse.model_fields
        assert getattr(get_settings(), key) is False, f"{key} 默认应为 False"


def test_user_without_personal_key_falls_back_to_global_key() -> None:
    base = Settings(
        llm_provider="openai",
        llm_model="gpt-4o",
        llm_api_key="global-secret-key-12345",
        llm_base_url="https://api.openai.com/v1",
    )
    # 用户仅切换模型或未配置 key
    overrides = {
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "llm_api_key": "",
    }
    effective = overlay_private(base, overrides)
    assert effective.llm_model == "gpt-4o-mini"
    assert effective.llm_api_key == "global-secret-key-12345", "未配置个人 key 时应复用全局 key"

    spec = resolve_llm_client_spec(effective)
    assert spec.api_key == "global-secret-key-12345"


def test_user_with_personal_key_uses_personal_key() -> None:
    base = Settings(
        llm_provider="openai",
        llm_model="gpt-4o",
        llm_api_key="global-secret-key-12345",
    )
    overrides = {
        "llm_provider": "openai",
        "llm_api_key": "my-personal-custom-key",
    }
    effective = overlay_private(base, overrides)
    assert effective.llm_api_key == "my-personal-custom-key"

    spec = resolve_llm_client_spec(effective)
    assert spec.api_key == "my-personal-custom-key"


def test_global_llm_keys_defined() -> None:
    assert "llm_provider" in GLOBAL_LLM_KEYS
    assert "llm_model" in GLOBAL_LLM_KEYS
    assert "llm_api_key" in GLOBAL_LLM_KEYS
    assert "llm_base_url" in GLOBAL_LLM_KEYS
