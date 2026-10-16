"""应用配置入口。

字段按领域拆分在 :mod:`app.configuration.groups`，这里组合成扁平 ``Settings``：

- 扁平访问 ``settings.llm_provider`` 保持不变（.env / 数据库 / 配置 API 契约）；
- 分组嵌套访问 ``settings.llm.provider`` 通过 :class:`GroupView` 提供（读写同一份状态）。

两者共享同一份字段，不存在第二份数据。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.configuration.groups import (
    BotGroup,
    DataSourceGroup,
    FeishuGroup,
    GroupView,
    IwencaiGroup,
    LLMGroup,
    MaintenanceGroup,
    NetworkGroup,
    NotionGroup,
    PushGroup,
    ResearchGroup,
    RuntimeGroup,
)
from app.configuration.locations import BACKEND_DIR, ROOT_DIR
from app.configuration.provider_catalog import PROVIDER_DEFAULTS

__all__ = ["BACKEND_DIR", "ROOT_DIR", "Settings"]


class Settings(
    LLMGroup,
    FeishuGroup,
    PushGroup,
    NotionGroup,
    IwencaiGroup,
    BotGroup,
    DataSourceGroup,
    NetworkGroup,
    MaintenanceGroup,
    ResearchGroup,
    RuntimeGroup,
    BaseSettings,
):
    """Purpose: 应用全局配置，从 .env 文件或环境变量加载 LLM、缓存、飞书、问财等模块的参数。"""

    model_config = SettingsConfigDict(
        env_file=[ROOT_DIR / ".env", BACKEND_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        hide_input_in_errors=True,
        extra="ignore",
    )

    # ---------------------------------------------------------------- 分组嵌套视图
    # 属性名 = 分组；字段名 = 扁平名去掉组前缀（见各组 PREFIX）。
    @property
    def llm(self) -> GroupView:
        return GroupView(self, LLMGroup)

    @property
    def feishu(self) -> GroupView:
        return GroupView(self, FeishuGroup)

    @property
    def push(self) -> GroupView:
        return GroupView(self, PushGroup)

    @property
    def notion(self) -> GroupView:
        return GroupView(self, NotionGroup)

    @property
    def iwencai(self) -> GroupView:
        return GroupView(self, IwencaiGroup)

    @property
    def bot(self) -> GroupView:
        return GroupView(self, BotGroup)

    @property
    def data_sources(self) -> GroupView:
        return GroupView(self, DataSourceGroup)

    @property
    def network(self) -> GroupView:
        return GroupView(self, NetworkGroup)

    @property
    def maintenance(self) -> GroupView:
        return GroupView(self, MaintenanceGroup)

    @property
    def research(self) -> GroupView:
        return GroupView(self, ResearchGroup)

    @property
    def runtime(self) -> GroupView:
        return GroupView(self, RuntimeGroup)

    # ---------------------------------------------------------------- 派生路径
    @property
    def quant_strategy_hash_ledger_path(self) -> Path:
        return self.app_data_dir / "quant-strategy-hashes.json"

    @property
    def quant_strategy_publish_dir(self) -> Path:
        return self.app_data_dir / "quant-strategies-published"

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """把相对路径解析为绝对路径（相对后端根目录）。"""
        if not self.app_data_dir.is_absolute():
            self.app_data_dir = BACKEND_DIR / self.app_data_dir
        self.app_data_dir = self.app_data_dir.resolve()
        if not self.quant_strategy_dir.is_absolute():
            self.quant_strategy_dir = BACKEND_DIR / self.quant_strategy_dir
        self.quant_strategy_dir = self.quant_strategy_dir.resolve()
        for field_name in ("database_backup_dir", "database_backup_mirror_dir"):
            path = getattr(self, field_name)
            if path is None:
                continue
            if not path.is_absolute():
                path = BACKEND_DIR / path
            setattr(self, field_name, path.resolve())
        return self

    @model_validator(mode="after")
    def _apply_provider_defaults(self) -> "Settings":
        """base_url/model 仍为默认值时，跟随所选 provider 的目录默认值。"""
        provider = self.llm_provider.lower()
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        default_base_url = Settings.model_fields["llm_base_url"].default
        default_model = Settings.model_fields["llm_model"].default
        if (not self.llm_base_url or self.llm_base_url == default_base_url) and "base_url" in defaults:
            self.llm_base_url = defaults["base_url"]
        if (not self.llm_model or self.llm_model == default_model) and "model" in defaults:
            self.llm_model = defaults["model"]
        if not self.llm_api_version and defaults.get("api_version"):
            self.llm_api_version = defaults["api_version"]
        return self

    @model_validator(mode="after")
    def _merge_legacy_feishu_credentials(self) -> "Settings":
        """飞书应用凭证合并：文档转存与 Bot 共用 feishu_app_*；
        旧部署只配了 BOT_FEISHU_APP_* 时回退继承，保证升级后仍可用。"""
        if not self.feishu_app_id and self.bot_feishu_app_id:
            self.feishu_app_id = self.bot_feishu_app_id
        if not self.feishu_app_secret and self.bot_feishu_app_secret:
            self.feishu_app_secret = self.bot_feishu_app_secret
        return self
