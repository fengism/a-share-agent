"""Unit tests for per-user effective settings overlay (app.config).

Covers value coercion, private-key-only overlay, empty-value fallback,
provider-default backfill, no-mutation of the global base, and per-user
isolation. The overlay algorithm was additionally validated by a standalone
stdlib mirror (the sandbox has no pydantic installed); these run under CI.
"""
from app import config as cfg


def test_coerce_types():
    assert cfg._coerce_setting_value("feishu_enabled", "true") is True
    assert cfg._coerce_setting_value("feishu_enabled", "0") is False
    assert cfg._coerce_setting_value("iwencai_enabled", "yes") is True
    assert cfg._coerce_setting_value("llm_temperature", "0.7") == 0.7
    assert cfg._coerce_setting_value("llm_api_key", "abc") == "abc"


def test_overlay_only_private_keys_and_skips_empty():
    base = cfg.get_settings()
    merged = cfg._overlay_private(
        base,
        {"llm_api_key": "K", "eastmoney_cookie": "IGNORED_GLOBAL", "llm_model": ""},
    )
    assert merged.llm_api_key == "K"
    # eastmoney_cookie is a GLOBAL key → never overlaid per-user
    assert merged.eastmoney_cookie == base.eastmoney_cookie
    # empty string = unset → falls back to base value
    assert merged.llm_model == base.llm_model
    # the global base object must not be mutated
    assert base.llm_api_key != "K"


def test_overlay_provider_default_backfill():
    base = cfg.get_settings()
    merged = cfg._overlay_private(base, {"llm_provider": "openai"})
    assert merged.llm_base_url == cfg.PROVIDER_DEFAULTS["openai"]["base_url"]
    assert merged.llm_model == cfg.PROVIDER_DEFAULTS["openai"]["model"]


def test_overlay_explicit_base_url_wins_over_provider_default():
    base = cfg.get_settings()
    merged = cfg._overlay_private(
        base, {"llm_provider": "openai", "llm_base_url": "https://proxy.local/v1"}
    )
    assert merged.llm_base_url == "https://proxy.local/v1"


def test_effective_settings_is_per_user(monkeypatch):
    monkeypatch.setattr(
        "app.db.user_store.get_user_config",
        lambda uid: {"llm_api_key": f"KEY_{uid}"},
    )
    s1 = cfg.effective_settings_for_user(1)
    s2 = cfg.effective_settings_for_user(2)
    assert s1.llm_api_key == "KEY_1"
    assert s2.llm_api_key == "KEY_2"


def test_effective_settings_none_returns_global_base():
    assert cfg.effective_settings_for_user(None) is cfg.get_settings()
