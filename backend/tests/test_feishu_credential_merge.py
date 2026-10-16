"""飞书应用凭证合并：文档转存与 Bot 共用 feishu_app_*。

兼容要求：
- 旧部署只配了 ``BOT_FEISHU_APP_ID`` / ``BOT_FEISHU_APP_SECRET`` 时，升级后仍可用；
- 管理员配置的 feishu_app_* 需同步到全局基线，供无用户上下文的 Bot 读取；
- 旧字段仍保留在 API/持久化白名单中，不破坏既有数据库行。
"""

from __future__ import annotations

from app.configuration import (
    GLOBAL_SYNCED_KEYS,
    PERSISTED_GLOBAL_KEYS,
    SECRET_KEYS,
    Settings,
)
from app.configuration.effective import overlay_private
from app.modules.bot.platforms import registry as bot_registry


def test_feishu_app_credentials_are_shared_and_synced() -> None:
    for key in ("feishu_app_id", "feishu_app_secret"):
        assert key in GLOBAL_SYNCED_KEYS, f"{key} 需同步到全局供后台 Bot 使用"
    assert "feishu_app_secret" in SECRET_KEYS
    # 旧字段继续保留，保证旧 .env 与旧数据库行可读
    assert "bot_feishu_app_id" in PERSISTED_GLOBAL_KEYS
    assert "bot_feishu_app_secret" in PERSISTED_GLOBAL_KEYS
    assert "bot_feishu_app_secret" in SECRET_KEYS


def test_legacy_bot_credentials_fall_back_to_shared() -> None:
    settings = Settings(
        feishu_app_id="",
        feishu_app_secret="",
        bot_feishu_app_id="cli_legacy",
        bot_feishu_app_secret="legacy-secret",
    )
    assert settings.feishu_app_id == "cli_legacy"
    assert settings.feishu_app_secret == "legacy-secret"


def test_explicit_shared_credentials_win() -> None:
    settings = Settings(
        feishu_app_id="cli_doc",
        feishu_app_secret="doc-secret",
        bot_feishu_app_id="cli_bot",
        bot_feishu_app_secret="bot-secret",
    )
    assert settings.feishu_app_id == "cli_doc"
    assert settings.feishu_app_secret == "doc-secret"


def test_user_override_does_not_resurrect_legacy_bot_value() -> None:
    base = Settings(
        feishu_app_id="cli_legacy",
        feishu_app_secret="legacy-secret",
    )
    effective = overlay_private(base, {"feishu_app_id": "cli_personal"})
    assert effective.feishu_app_id == "cli_personal"
    assert effective.feishu_app_secret == "legacy-secret"


def test_bot_registry_prefers_bot_credentials_then_shared(monkeypatch) -> None:
    legacy = Settings(bot_feishu_app_id="cli_bot", bot_feishu_app_secret="bot-secret")
    monkeypatch.setattr(bot_registry, "get_settings", lambda: legacy)
    scoped = bot_registry.get_bot_feishu_settings()
    assert scoped.feishu_app_id == "cli_bot"
    assert scoped.feishu_app_secret == "bot-secret"

    shared = Settings(feishu_app_id="cli_shared", feishu_app_secret="shared-secret")
    monkeypatch.setattr(bot_registry, "get_settings", lambda: shared)
    scoped = bot_registry.get_bot_feishu_settings()
    assert scoped.feishu_app_id == "cli_shared"
    assert scoped.feishu_app_secret == "shared-secret"
