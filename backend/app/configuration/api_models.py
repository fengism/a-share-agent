"""配置 API 契约与派生元数据（单一事实来源）。

设计目标：**同一份配置只声明一次**。每个字段用 ``Annotated[..., ConfigMeta]``
内联标注 scope / secret / synced / group，``PRIVATE_USER_KEYS``、
``PERSISTED_GLOBAL_KEYS``、``GLOBAL_SYNCED_KEYS``、``SECRET_KEYS`` 与
``ConfigResponse`` 全部由此派生，避免多处手工清单漂移。

- scope=private: 每个登录用户可覆盖（落 ``user_config``）
- scope=global:  仅管理员可改（落 ``global_config``）
- synced_global: private 字段中，管理员保存时额外同步到全局基线，供无用户
  上下文的常驻后台任务复用（大模型与推送通道即此模式）
- secret:        入库加密、接口下发时脱敏

约定：``ConfigUpdateRequest`` 字段集合即接口可编辑字段全集；新增配置项必须
在此登记，否则不会被持久化，并会被 ``extra="forbid"`` 拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.configuration.provider_catalog import LLMApiMode

__all__ = [
    "API_SECRET_KEYS",
    "CONFIG_FIELD_GROUPS",
    "CONFIG_VALUE_FIELDS",
    "ConfigMeta",
    "ConfigResponse",
    "ConfigUpdateRequest",
    "GLOBAL_LLM_KEYS",
    "GLOBAL_PUSH_KEYS",
    "GLOBAL_STORAGE_KEYS",
    "GLOBAL_SYNCED_KEYS",
    "NON_API_SECRET_KEYS",
    "PERSISTED_GLOBAL_KEYS",
    "PRIVATE_USER_KEYS",
    "SECRET_KEYS",
]

Scope = Literal["private", "global"]


@dataclass(frozen=True, slots=True)
class ConfigMeta:
    """字段级配置元数据；pydantic 保留但不会写入 OpenAPI。"""

    scope: Scope
    group: str
    secret: bool = False
    synced_global: bool = False


class ConfigUpdateRequest(BaseModel):
    """Partial configuration update request (per-user private + admin global)."""

    model_config = ConfigDict(extra="forbid")

    # ---------------------------------------------------------------- 大模型
    llm_provider: Annotated[str | None, ConfigMeta("private", "llm", synced_global=True)] = None
    llm_api_mode: Annotated[
        LLMApiMode | None,
        ConfigMeta("private", "llm", synced_global=True),
    ] = None
    llm_api_version: Annotated[str | None, ConfigMeta("private", "llm", synced_global=True)] = None
    llm_api_key: Annotated[
        str | None, ConfigMeta("private", "llm", secret=True, synced_global=True)
    ] = None
    llm_base_url: Annotated[str | None, ConfigMeta("private", "llm", synced_global=True)] = None
    llm_model: Annotated[str | None, ConfigMeta("private", "llm", synced_global=True)] = None
    llm_sub_model: Annotated[str | None, ConfigMeta("private", "llm", synced_global=True)] = None
    llm_simple_tasks: Annotated[str | None, ConfigMeta("private", "llm", synced_global=True)] = None
    llm_temperature: Annotated[
        float | None, ConfigMeta("private", "llm", synced_global=True)
    ] = None
    llm_context_length_tokens: Annotated[
        int | None, ConfigMeta("private", "llm", synced_global=True)
    ] = Field(default=None, ge=0)

    # ---------------------------------------------------------------- 飞书文档
    feishu_enabled: Annotated[bool | None, ConfigMeta("private", "feishu")] = None
    feishu_app_id: Annotated[
        str | None, ConfigMeta("private", "feishu", synced_global=True)
    ] = None
    feishu_app_secret: Annotated[
        str | None, ConfigMeta("private", "feishu", secret=True, synced_global=True)
    ] = None
    feishu_folder_token: Annotated[
        str | None, ConfigMeta("private", "feishu", secret=True)
    ] = None
    feishu_wiki_space_id: Annotated[str | None, ConfigMeta("private", "feishu")] = None
    feishu_wiki_daily_review_parent: Annotated[str | None, ConfigMeta("private", "feishu")] = None
    feishu_wiki_analysis_parent: Annotated[str | None, ConfigMeta("private", "feishu")] = None
    feishu_daily_review_folder: Annotated[str | None, ConfigMeta("private", "feishu")] = None
    feishu_analysis_folder: Annotated[str | None, ConfigMeta("private", "feishu")] = None
    feishu_default_receiver: Annotated[str | None, ConfigMeta("private", "feishu")] = None

    # ---------------------------------------------------------------- 推送通道
    push_auto_enabled: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    push_daily_review_auto: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    push_potential_auto: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    push_feishu_enabled: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    feishu_webhook_url: Annotated[
        str | None, ConfigMeta("private", "push", secret=True, synced_global=True)
    ] = None
    feishu_webhook_secret: Annotated[
        str | None, ConfigMeta("private", "push", secret=True, synced_global=True)
    ] = None
    push_dingtalk_enabled: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    dingtalk_webhook_url: Annotated[
        str | None, ConfigMeta("private", "push", secret=True, synced_global=True)
    ] = None
    dingtalk_webhook_secret: Annotated[
        str | None, ConfigMeta("private", "push", secret=True, synced_global=True)
    ] = None
    push_wecom_enabled: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    wecom_webhook_url: Annotated[
        str | None, ConfigMeta("private", "push", secret=True, synced_global=True)
    ] = None
    push_wxpusher_enabled: Annotated[
        bool | None, ConfigMeta("private", "push", synced_global=True)
    ] = None
    wxpusher_app_token: Annotated[
        str | None, ConfigMeta("private", "push", secret=True, synced_global=True)
    ] = None
    wxpusher_uids: Annotated[
        str | None, ConfigMeta("private", "push", synced_global=True)
    ] = None

    # ---------------------------------------------------------------- Notion
    notion_enabled: Annotated[bool | None, ConfigMeta("private", "notion")] = None
    notion_api_token: Annotated[str | None, ConfigMeta("private", "notion", secret=True)] = None
    notion_parent_page_id: Annotated[str | None, ConfigMeta("private", "notion")] = None
    notion_database_id: Annotated[str | None, ConfigMeta("private", "notion")] = None

    # ---------------------------------------------------------------- 问财
    iwencai_enabled: Annotated[bool | None, ConfigMeta("private", "iwencai")] = None
    iwencai_base_url: Annotated[str | None, ConfigMeta("private", "iwencai")] = None
    iwencai_api_key: Annotated[str | None, ConfigMeta("private", "iwencai", secret=True)] = None

    # ---------------------------------------------------------------- Chat 能力
    disabled_chat_skills: Annotated[list[str] | None, ConfigMeta("private", "capabilities")] = None
    disabled_chat_agents: Annotated[list[str] | None, ConfigMeta("private", "capabilities")] = None

    # ---------------------------------------------------------------- 网络与数据源
    http_trust_env: Annotated[bool | None, ConfigMeta("global", "network")] = None
    twitter_feeds: Annotated[list[str] | None, ConfigMeta("global", "data_sources")] = None
    eastmoney_cookie: Annotated[
        str | None, ConfigMeta("global", "eastmoney", secret=True)
    ] = None
    fred_api_key: Annotated[str | None, ConfigMeta("global", "data_sources", secret=True)] = None
    anysearch_api_key: Annotated[
        str | None, ConfigMeta("global", "data_sources", secret=True)
    ] = None
    fuyao_api_key: Annotated[str | None, ConfigMeta("global", "data_sources", secret=True)] = None
    baidu_cookie: Annotated[str | None, ConfigMeta("global", "data_sources", secret=True)] = None
    ths_cookie: Annotated[str | None, ConfigMeta("global", "data_sources", secret=True)] = None
    legulegu_token: Annotated[
        str | None, ConfigMeta("global", "data_sources", secret=True)
    ] = None

    # ---------------------------------------------------------------- 东财限流
    eastmoney_min_interval_seconds: Annotated[
        float | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=0, le=60)
    eastmoney_datacenter_min_interval_seconds: Annotated[
        float | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=0, le=60)
    eastmoney_datacenter_cooldown_seconds: Annotated[
        float | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=0, le=86400)
    eastmoney_jitter_min_seconds: Annotated[
        float | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=0, le=60)
    eastmoney_jitter_max_seconds: Annotated[
        float | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=0, le=60)
    eastmoney_cooldown_seconds: Annotated[
        float | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=0, le=86400)
    eastmoney_transient_failure_threshold: Annotated[
        int | None, ConfigMeta("global", "eastmoney")
    ] = Field(default=None, ge=1, le=100)

    # ---------------------------------------------------------------- 出站代理
    outbound_proxy_type: Annotated[
        Literal["none", "http", "socks5"] | None, ConfigMeta("global", "proxy")
    ] = None
    outbound_proxy_url: Annotated[
        str | None, ConfigMeta("global", "proxy", secret=True)
    ] = Field(default=None, max_length=512)
    outbound_proxy_timeout_seconds: Annotated[
        float | None, ConfigMeta("global", "proxy")
    ] = Field(default=None, ge=5, le=120)
    outbound_proxy_retries: Annotated[
        int | None, ConfigMeta("global", "proxy")
    ] = Field(default=None, ge=0, le=6)

    # ---------------------------------------------------------------- 行情归档
    market_daily_bar_refresh_enabled: Annotated[
        bool | None, ConfigMeta("global", "maintenance")
    ] = None
    market_daily_bar_refresh_poll_seconds: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=15, le=3600)
    market_daily_bar_refresh_retry_base_seconds: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=1, le=1800)
    market_daily_observation_retention_days: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=7, le=3650)
    market_daily_attempt_retention_days: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=30, le=3650)

    # ---------------------------------------------------------------- 常驻任务开关
    macro_analysis_prewarm_enabled: Annotated[
        bool | None, ConfigMeta("global", "maintenance")
    ] = None
    daily_review_prewarm_enabled: Annotated[
        bool | None, ConfigMeta("global", "maintenance")
    ] = None
    potential_stock_daily_enabled: Annotated[
        bool | None, ConfigMeta("global", "maintenance")
    ] = None
    stock_valuation_snapshot_refresh_enabled: Annotated[
        bool | None, ConfigMeta("global", "maintenance")
    ] = None

    # ---------------------------------------------------------------- 备份策略
    database_backup_retention_count: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=1, le=90)
    database_backup_include_market_daily: Annotated[
        bool | None, ConfigMeta("global", "maintenance")
    ] = None
    market_daily_backup_interval_days: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=1, le=90)
    market_daily_backup_compression_level: Annotated[
        int | None, ConfigMeta("global", "maintenance")
    ] = Field(default=None, ge=1, le=9)

    # ---------------------------------------------------------------- 飞书 Bot
    bot_enabled: Annotated[bool | None, ConfigMeta("global", "bot")] = None
    bot_command_prefix: Annotated[str | None, ConfigMeta("global", "bot")] = Field(
        default=None, min_length=1, max_length=4
    )
    bot_service_user_id: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=0
    )
    bot_feishu_app_id: Annotated[str | None, ConfigMeta("global", "bot")] = None
    # 已弃用：Bot 现复用 feishu_app_secret；保留仅为兼容旧部署（优先于共享值）
    bot_feishu_app_secret: Annotated[
        str | None, ConfigMeta("global", "bot", secret=True)
    ] = None
    feishu_verification_token: Annotated[
        str | None, ConfigMeta("global", "bot", secret=True)
    ] = None
    feishu_encrypt_key: Annotated[str | None, ConfigMeta("global", "bot", secret=True)] = None
    bot_rate_limit_requests: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=1000
    )
    bot_rate_limit_window: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=86400
    )
    bot_webhook_max_skew_seconds: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=3600
    )
    bot_event_dedup_ttl_seconds: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=604800
    )
    bot_job_poll_seconds: Annotated[float | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=0.1, le=60
    )
    bot_job_lease_seconds: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=30, le=86400
    )
    bot_job_max_attempts: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=20
    )
    bot_job_retry_base_seconds: Annotated[float | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=0, le=3600
    )
    bot_job_worker_concurrency: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=8
    )
    bot_batch_concurrency: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=8
    )
    bot_batch_max_stocks: Annotated[int | None, ConfigMeta("global", "bot")] = Field(
        default=None, ge=1, le=50
    )
    bot_admin_users: Annotated[list[str] | None, ConfigMeta("global", "bot")] = None

    # ---------------------------------------------------------------- 调研预算
    industry_chain_research_timeout_seconds: Annotated[
        float | None, ConfigMeta("global", "research")
    ] = Field(default=None, gt=0)
    industry_chain_repair_research_timeout_seconds: Annotated[
        float | None, ConfigMeta("global", "research")
    ] = Field(default=None, gt=0)
    industry_chain_repair_synthesis_timeout_seconds: Annotated[
        float | None, ConfigMeta("global", "research")
    ] = Field(default=None, gt=0)
    industry_chain_max_rounds: Annotated[int | None, ConfigMeta("global", "research")] = Field(
        default=None, ge=2, le=10
    )
    industry_chain_repair_max_rounds: Annotated[
        int | None, ConfigMeta("global", "research")
    ] = Field(default=None, ge=1, le=6)
    industry_chain_tool_calls_total: Annotated[
        int | None, ConfigMeta("global", "research")
    ] = Field(default=None, ge=8, le=128)
    industry_chain_repair_tool_calls_total: Annotated[
        int | None, ConfigMeta("global", "research")
    ] = Field(default=None, ge=4, le=64)
    analysis_llm_timeout_seconds: Annotated[
        float | None, ConfigMeta("global", "research")
    ] = Field(default=None, gt=0)
    agent_research_timeout_seconds: Annotated[
        float | None, ConfigMeta("global", "research")
    ] = Field(default=None, gt=0)
    chat_max_tool_calls_total: Annotated[int | None, ConfigMeta("global", "research")] = Field(
        default=None, ge=1, le=128
    )


# ---------------------------------------------------------------------------
# 派生集合
# ---------------------------------------------------------------------------

def _meta_of(name: str) -> ConfigMeta:
    for item in ConfigUpdateRequest.model_fields[name].metadata:
        if isinstance(item, ConfigMeta):
            return item
    raise RuntimeError(f"字段 {name} 缺少 ConfigMeta 元数据")


CONFIG_VALUE_FIELDS = frozenset(ConfigUpdateRequest.model_fields)
PRIVATE_USER_KEYS = frozenset(
    name for name in CONFIG_VALUE_FIELDS if _meta_of(name).scope == "private"
)
PERSISTED_GLOBAL_KEYS = frozenset(
    name for name in CONFIG_VALUE_FIELDS if _meta_of(name).scope == "global"
)
GLOBAL_LLM_KEYS = frozenset(
    name
    for name in CONFIG_VALUE_FIELDS
    if _meta_of(name).group == "llm" and _meta_of(name).synced_global
)
GLOBAL_PUSH_KEYS = frozenset(
    name
    for name in CONFIG_VALUE_FIELDS
    if _meta_of(name).group == "push" and _meta_of(name).synced_global
)
# 管理员保存时需额外同步到全局基线的字段（大模型 + 推送通道 + 共享飞书应用凭证）。
# 常驻后台任务（收盘推送、飞书 Bot）无用户上下文，只能读到全局基线。
GLOBAL_SYNCED_KEYS = frozenset(
    name for name in CONFIG_VALUE_FIELDS if _meta_of(name).synced_global
)
# 全局配置存储允许读写的键：管理员专属项 + 需同步到全局的 private 项
GLOBAL_STORAGE_KEYS = PERSISTED_GLOBAL_KEYS | GLOBAL_SYNCED_KEYS

# 接口可编辑的敏感字段
API_SECRET_KEYS = frozenset(name for name in CONFIG_VALUE_FIELDS if _meta_of(name).secret)
# 不通过配置接口暴露、但仍需加密与脱敏的敏感字段
NON_API_SECRET_KEYS = frozenset({"python_sandbox_token", "baidu_acs_token"})
SECRET_KEYS = API_SECRET_KEYS | NON_API_SECRET_KEYS

# group -> 字段名（文档与前端分组使用）
CONFIG_FIELD_GROUPS: dict[str, tuple[str, ...]] = {}
for _name in CONFIG_VALUE_FIELDS:
    _group = _meta_of(_name).group
    CONFIG_FIELD_GROUPS[_group] = (*CONFIG_FIELD_GROUPS.get(_group, ()), _name)


# ---------------------------------------------------------------------------
# 由 ConfigUpdateRequest 派生只读响应模型（字段必填，另含元信息字段）
# ---------------------------------------------------------------------------

def _required_annotation(annotation):
    """去掉 Optional 的 None 分支，得到响应模型的必填类型。"""
    args = get_args(annotation)
    if not args:
        return annotation
    non_none = tuple(arg for arg in args if arg is not type(None))
    return non_none[0] if len(non_none) == 1 else annotation


ConfigResponse = create_model(
    "ConfigResponse",
    __module__=__name__,
    __doc__="Current effective configuration with secrets masked.",
    **{
        name: (_required_annotation(field.annotation), ...)
        for name, field in ConfigUpdateRequest.model_fields.items()
    },
    provider_defaults=(dict, ...),
    is_admin=(bool, ...),
)
