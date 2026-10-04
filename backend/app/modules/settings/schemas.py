from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.configuration.schema import PERSISTED_GLOBAL_KEYS, PRIVATE_USER_KEYS


class ConfigResponse(BaseModel):
    """Current effective configuration with secrets masked."""

    llm_provider: str
    llm_api_mode: Literal["auto", "openai", "litellm"]
    llm_api_version: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    llm_context_length_tokens: int
    feishu_enabled: bool
    feishu_app_id: str
    feishu_app_secret: str
    feishu_folder_token: str
    feishu_wiki_space_id: str
    feishu_wiki_daily_review_parent: str
    feishu_wiki_analysis_parent: str
    feishu_daily_review_folder: str
    feishu_analysis_folder: str
    feishu_default_receiver: str
    notion_enabled: bool
    notion_api_token: str
    notion_parent_page_id: str
    notion_database_id: str
    iwencai_enabled: bool
    iwencai_base_url: str
    iwencai_api_key: str
    disabled_chat_skills: list[str]
    disabled_chat_agents: list[str]
    http_trust_env: bool
    provider_defaults: dict
    twitter_feeds: list[str]
    eastmoney_cookie: str
    fred_api_key: str
    anysearch_api_key: str
    baidu_cookie: str
    ths_cookie: str
    legulegu_token: str
    eastmoney_min_interval_seconds: float
    eastmoney_datacenter_min_interval_seconds: float
    eastmoney_datacenter_cooldown_seconds: float
    eastmoney_jitter_min_seconds: float
    eastmoney_jitter_max_seconds: float
    eastmoney_cooldown_seconds: float
    eastmoney_transient_failure_threshold: int
    market_daily_bar_refresh_enabled: bool
    market_daily_bar_refresh_poll_seconds: int
    market_daily_bar_refresh_retry_base_seconds: int
    market_daily_observation_retention_days: int
    market_daily_attempt_retention_days: int
    bot_enabled: bool
    bot_command_prefix: str
    bot_service_user_id: int
    bot_feishu_app_id: str
    bot_feishu_app_secret: str
    feishu_verification_token: str
    feishu_encrypt_key: str
    bot_rate_limit_requests: int
    bot_rate_limit_window: int
    bot_webhook_max_skew_seconds: int
    bot_event_dedup_ttl_seconds: int
    bot_job_poll_seconds: float
    bot_job_lease_seconds: int
    bot_job_max_attempts: int
    bot_job_retry_base_seconds: float
    bot_job_worker_concurrency: int
    bot_batch_concurrency: int
    bot_batch_max_stocks: int
    bot_admin_users: list[str]
    industry_chain_research_timeout_seconds: float
    industry_chain_repair_research_timeout_seconds: float
    industry_chain_repair_synthesis_timeout_seconds: float
    industry_chain_max_rounds: int
    industry_chain_repair_max_rounds: int
    industry_chain_tool_calls_total: int
    industry_chain_repair_tool_calls_total: int
    analysis_llm_timeout_seconds: float
    agent_research_timeout_seconds: float
    chat_max_tool_calls_total: int
    database_backup_retention_count: int
    database_backup_include_market_daily: bool
    market_daily_backup_interval_days: int
    market_daily_backup_compression_level: int
    is_admin: bool


class ConfigUpdateRequest(BaseModel):
    """Partial configuration update request."""

    llm_provider: str | None = None
    llm_api_mode: Literal["auto", "openai", "litellm"] | None = None
    llm_api_version: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    llm_context_length_tokens: int | None = Field(default=None, ge=0)
    feishu_enabled: bool | None = None
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_folder_token: str | None = None
    feishu_wiki_space_id: str | None = None
    feishu_wiki_daily_review_parent: str | None = None
    feishu_wiki_analysis_parent: str | None = None
    feishu_daily_review_folder: str | None = None
    feishu_analysis_folder: str | None = None
    feishu_default_receiver: str | None = None
    notion_enabled: bool | None = None
    notion_api_token: str | None = None
    notion_parent_page_id: str | None = None
    notion_database_id: str | None = None
    iwencai_enabled: bool | None = None
    iwencai_base_url: str | None = None
    iwencai_api_key: str | None = None
    disabled_chat_skills: list[str] | None = None
    disabled_chat_agents: list[str] | None = None
    http_trust_env: bool | None = None
    twitter_feeds: list[str] | None = None
    eastmoney_cookie: str | None = None
    fred_api_key: str | None = None
    anysearch_api_key: str | None = None
    baidu_cookie: str | None = None
    ths_cookie: str | None = None
    legulegu_token: str | None = None
    eastmoney_min_interval_seconds: float | None = Field(default=None, ge=0, le=60)
    eastmoney_datacenter_min_interval_seconds: float | None = Field(default=None, ge=0, le=60)
    eastmoney_datacenter_cooldown_seconds: float | None = Field(default=None, ge=0, le=86400)
    eastmoney_jitter_min_seconds: float | None = Field(default=None, ge=0, le=60)
    eastmoney_jitter_max_seconds: float | None = Field(default=None, ge=0, le=60)
    eastmoney_cooldown_seconds: float | None = Field(default=None, ge=0, le=86400)
    eastmoney_transient_failure_threshold: int | None = Field(default=None, ge=1, le=100)
    market_daily_bar_refresh_enabled: bool | None = None
    market_daily_bar_refresh_poll_seconds: int | None = Field(default=None, ge=15, le=3600)
    market_daily_bar_refresh_retry_base_seconds: int | None = Field(default=None, ge=1, le=1800)
    market_daily_observation_retention_days: int | None = Field(default=None, ge=7, le=3650)
    market_daily_attempt_retention_days: int | None = Field(default=None, ge=30, le=3650)
    database_backup_retention_count: int | None = Field(default=None, ge=1, le=90)
    database_backup_include_market_daily: bool | None = None
    market_daily_backup_interval_days: int | None = Field(default=None, ge=1, le=90)
    market_daily_backup_compression_level: int | None = Field(default=None, ge=1, le=9)
    bot_enabled: bool | None = None
    bot_command_prefix: str | None = Field(default=None, min_length=1, max_length=4)
    bot_service_user_id: int | None = Field(default=None, ge=0)
    bot_feishu_app_id: str | None = None
    bot_feishu_app_secret: str | None = None
    feishu_verification_token: str | None = None
    feishu_encrypt_key: str | None = None
    bot_rate_limit_requests: int | None = Field(default=None, ge=1, le=1000)
    bot_rate_limit_window: int | None = Field(default=None, ge=1, le=86400)
    bot_webhook_max_skew_seconds: int | None = Field(default=None, ge=1, le=3600)
    bot_event_dedup_ttl_seconds: int | None = Field(default=None, ge=1, le=604800)
    bot_job_poll_seconds: float | None = Field(default=None, ge=0.1, le=60)
    bot_job_lease_seconds: int | None = Field(default=None, ge=30, le=86400)
    bot_job_max_attempts: int | None = Field(default=None, ge=1, le=20)
    bot_job_retry_base_seconds: float | None = Field(default=None, ge=0, le=3600)
    bot_job_worker_concurrency: int | None = Field(default=None, ge=1, le=8)
    bot_batch_concurrency: int | None = Field(default=None, ge=1, le=8)
    bot_batch_max_stocks: int | None = Field(default=None, ge=1, le=50)
    bot_admin_users: list[str] | None = None
    industry_chain_research_timeout_seconds: float | None = Field(default=None, gt=0)
    industry_chain_repair_research_timeout_seconds: float | None = Field(default=None, gt=0)
    industry_chain_repair_synthesis_timeout_seconds: float | None = Field(default=None, gt=0)
    industry_chain_max_rounds: int | None = Field(default=None, ge=2, le=10)
    industry_chain_repair_max_rounds: int | None = Field(default=None, ge=1, le=6)
    industry_chain_tool_calls_total: int | None = Field(default=None, ge=8, le=128)
    industry_chain_repair_tool_calls_total: int | None = Field(default=None, ge=4, le=64)
    analysis_llm_timeout_seconds: float | None = Field(default=None, gt=0)
    agent_research_timeout_seconds: float | None = Field(default=None, gt=0)
    chat_max_tool_calls_total: int | None = Field(default=None, ge=1, le=128)


class LlmModelsRequest(BaseModel):
    """按 Base URL + API Key 拉取 OpenAI 兼容 /models 列表的请求。"""

    base_url: str = ""
    api_key: str = ""
    api_mode: str = ""
    api_version: str = ""


class LlmModelsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)


CONFIG_RESPONSE_META_FIELDS = frozenset({"provider_defaults", "is_admin"})
CONFIG_VALUE_FIELDS = frozenset(ConfigUpdateRequest.model_fields)
if frozenset(ConfigResponse.model_fields) - CONFIG_RESPONSE_META_FIELDS != CONFIG_VALUE_FIELDS:
    raise RuntimeError("ConfigResponse 与 ConfigUpdateRequest 字段定义不一致")
if CONFIG_VALUE_FIELDS - PRIVATE_USER_KEYS != PERSISTED_GLOBAL_KEYS:
    raise RuntimeError("ConfigUpdateRequest 全局字段与持久化白名单不一致")
