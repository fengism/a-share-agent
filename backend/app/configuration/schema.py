from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.configuration.llm_compatibility import LLMCompatibilityOverride
from app.configuration.provider_catalog import PROVIDER_DEFAULTS

if TYPE_CHECKING:
    from app.configuration.views import (
        IntegrationSettingsView,
        LLMSettingsView,
        ProviderSettingsView,
        RuntimeSettingsView,
        WorkerSettingsView,
    )

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent

PRIVATE_USER_KEYS = frozenset(
    {
        "llm_provider",
        "llm_api_mode",
        "llm_api_version",
        "llm_api_key",
        "llm_base_url",
        "llm_model",
        "llm_temperature",
        "llm_context_length_tokens",
        "notion_enabled",
        "notion_api_token",
        "notion_parent_page_id",
        "notion_database_id",
        "feishu_enabled",
        "feishu_app_id",
        "feishu_app_secret",
        "feishu_folder_token",
        "feishu_wiki_space_id",
        "feishu_wiki_daily_review_parent",
        "feishu_wiki_analysis_parent",
        "feishu_daily_review_folder",
        "feishu_analysis_folder",
        "feishu_default_receiver",
        "iwencai_enabled",
        "iwencai_base_url",
        "iwencai_api_key",
        "disabled_chat_skills",
        "disabled_chat_agents",
    }
)

PERSISTED_GLOBAL_KEYS = frozenset(
    {
        "http_trust_env",
        "twitter_feeds",
        "eastmoney_cookie",
        "fred_api_key",
        "anysearch_api_key",
        "baidu_cookie",
        "ths_cookie",
        "legulegu_token",
        "eastmoney_min_interval_seconds",
        "eastmoney_datacenter_min_interval_seconds",
        "eastmoney_datacenter_cooldown_seconds",
        "eastmoney_jitter_min_seconds",
        "eastmoney_jitter_max_seconds",
        "eastmoney_cooldown_seconds",
        "eastmoney_transient_failure_threshold",
        "outbound_proxy_type",
        "outbound_proxy_url",
        "outbound_proxy_timeout_seconds",
        "outbound_proxy_retries",
        "market_daily_bar_refresh_enabled",
        "market_daily_bar_refresh_poll_seconds",
        "market_daily_bar_refresh_retry_base_seconds",
        "market_daily_observation_retention_days",
        "market_daily_attempt_retention_days",
        "database_backup_retention_count",
        "database_backup_include_market_daily",
        "market_daily_backup_interval_days",
        "market_daily_backup_compression_level",
        "bot_enabled",
        "bot_command_prefix",
        "bot_service_user_id",
        "bot_rate_limit_requests",
        "bot_rate_limit_window",
        "bot_webhook_max_skew_seconds",
        "bot_event_dedup_ttl_seconds",
        "bot_job_poll_seconds",
        "industry_chain_research_timeout_seconds",
        "industry_chain_repair_research_timeout_seconds",
        "industry_chain_repair_synthesis_timeout_seconds",
        "industry_chain_max_rounds",
        "industry_chain_repair_max_rounds",
        "industry_chain_tool_calls_total",
        "industry_chain_repair_tool_calls_total",
        "analysis_llm_timeout_seconds",
        "agent_research_timeout_seconds",
        "chat_max_tool_calls_total",
        "bot_job_lease_seconds",
        "bot_job_max_attempts",
        "bot_job_retry_base_seconds",
        "bot_job_worker_concurrency",
        "bot_batch_concurrency",
        "bot_batch_max_stocks",
        "bot_admin_users",
        "bot_feishu_app_id",
        "bot_feishu_app_secret",
        "feishu_verification_token",
        "feishu_encrypt_key",
    }
)

SECRET_KEYS = frozenset(
    {
        "python_sandbox_token",
        "anysearch_api_key",
        "llm_api_key",
        "feishu_app_secret",
        "feishu_verification_token",
        "feishu_encrypt_key",
        "bot_feishu_app_secret",
        "iwencai_api_key",
        "notion_api_token",
        "eastmoney_cookie",
        "fred_api_key",
        "baidu_cookie",
        "baidu_acs_token",
        "ths_cookie",
        "legulegu_token",
        # 代理地址内含用户名密码，按凭证处理避免在配置接口中明文下发
        "outbound_proxy_url",
    }
)


class Settings(BaseSettings):
    """Purpose: 应用全局配置，从 .env 文件或环境变量加载 LLM、缓存、飞书、问财等模块的参数。"""

    model_config = SettingsConfigDict(
        env_file=[ROOT_DIR / ".env", BACKEND_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        hide_input_in_errors=True,
        extra="ignore",
    )

    llm_provider: str = "deepseek"
    llm_api_mode: Literal["auto", "openai", "litellm"] = "auto"
    llm_api_version: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    llm_temperature: float = 0.1
    # 模型上下文长度（tokens）；0 表示未设置，历史裁剪沿用默认 40k 字符预算。
    llm_context_length_tokens: int = Field(default=0, ge=0)
    llm_timeout_seconds: int = Field(default=300, gt=0)
    # Deployment policy; current provider/model is never changed by these limits.
    llm_generation_timeout_seconds: float = Field(default=1200.0, gt=0)
    llm_generation_max_completion_tokens: int = Field(default=8192, ge=1)
    llm_max_attempts: int = Field(default=2, ge=1, le=3)
    llm_model_max_completion_tokens: int | None = Field(default=None, ge=1)
    llm_stream_include_usage: bool = True
    llm_json_mode_enabled: bool = True
    llm_compatibility_overrides: list[LLMCompatibilityOverride] = Field(default_factory=list, repr=False)
    agent_research_timeout_seconds: float = Field(default=1200.0, gt=0)
    # 产业链调研预算独立于交互式 Chat/通用 Agent；有进展时允许更多轮次，无进展仍提前停止。
    industry_chain_tool_calls_total: int = Field(default=96, ge=8, le=128)
    industry_chain_repair_tool_calls_total: int = Field(default=48, ge=4, le=64)
    industry_chain_max_rounds: int = Field(default=6, ge=2, le=10)
    industry_chain_repair_max_rounds: int = Field(default=3, ge=1, le=6)
    industry_chain_research_timeout_seconds: float = Field(default=1800.0, gt=0)
    # 产业链定向补证分为独立的取证与报告重写时限；任一阶段超时都保留初稿并标记 degraded。
    industry_chain_repair_research_timeout_seconds: float = Field(default=900.0, gt=0)
    industry_chain_repair_synthesis_timeout_seconds: float = Field(default=600.0, gt=0)
    # Long report generation: one deadline shared by streaming and schema repair.
    analysis_llm_timeout_seconds: float = Field(default=1200.0, gt=0)
    analysis_llm_max_completion_tokens: int = Field(default=32768, ge=1)

    # Deployment-only; deliberately absent from private/persisted editable keys.
    pdf_max_concurrency: int = Field(default=1, ge=1, le=4)
    pdf_max_waiters: int = Field(default=4, ge=0, le=32)
    pdf_render_timeout_seconds: float = Field(default=120.0, gt=0, le=240.0)
    python_sandbox_url: str = ""
    python_sandbox_token: str = Field(default="", repr=False)

    # 缓存 TTL 必须为正整数：TTLCache.set 对 ttl<=0 直接抛 ValueError，
    # 零值配置若在启动时不拦截，会在运行时把对应接口全部打挂
    cache_ttl_analysis: int = Field(default=14400, ge=1)
    analysis_page_section_timeout_seconds: float = Field(default=15.0, gt=0)
    market_statistics_section_timeout_seconds: float = Field(default=15.0, gt=0)
    app_data_dir: Path = BACKEND_DIR / "data"
    portfolio_quote_cache_ttl_seconds: int = Field(default=10, ge=1)
    portfolio_quote_stale_ttl_seconds: int = Field(default=300, ge=1)
    update_hub_namespace: str = "fengliu1989"
    update_hub_repo: str = "a-share-backend"
    quant_strategy_dir: Path = BACKEND_DIR / "app" / "modules" / "quant" / "strategies" / "definitions"
    quant_strategy_reload_seconds: float = Field(default=5.0, ge=1.0, le=3600.0)
    # 产业链知识库外部导入目录：与用户存档根目录（data/industry_chains）分离，
    # 避免存档目录树被知识库 loader 的 glob 误扫
    industry_atlas_import_dir: Path = BACKEND_DIR / "data" / "industry_atlas_imports"
    # AI 产业链分析完成后是否自动挖掘进知识库（同名链稳定覆盖）
    industry_atlas_auto_mining: bool = True

    max_concurrent_chat_per_user: int = 2
    max_concurrent_chat_total: int = 8
    max_concurrent_llm_requests: int = 6
    blocking_thread_pool_workers: int = 20
    chat_max_completion_tokens: int = 4096
    chat_total_timeout_seconds: int = 300
    chat_heartbeat_seconds: int = 15
    chat_tool_timeout_seconds: int = 45
    # Maximum new calls in an execution batch, not a hard cap on one model turn.
    chat_max_tool_calls_per_round: int = Field(default=16, ge=1, le=32)
    chat_max_tool_calls_total: int = Field(default=32, ge=1, le=128)
    chat_max_tool_context_characters: int = Field(default=60_000, ge=4_096, le=500_000)
    chat_max_synthesis_characters: int = Field(default=60_000, ge=4_096, le=500_000)

    provider_gateway_max_attempts: int = 2
    provider_failure_threshold: int = 3
    provider_circuit_open_seconds: float = 30.0
    provider_retry_base_seconds: float = 0.2
    provider_retry_budget_seconds: float = 5.0
    provider_retry_jitter_seconds: float = 0.1

    tdxhub_timeout_seconds: float = Field(default=5.0, gt=0)
    # 客户端重建失败的冷却窗口。SDK 每次重建都会全量探测候选行情服务器，
    # 冷却期内快速失败可避免故障期间反复付出探测代价；到期后自动重新探测，
    # 恢复的服务器会自然重新参与，因此该值只影响恢复延迟、不影响可用性。
    tdxhub_rebuild_cooldown_seconds: float = Field(default=30.0, ge=0, le=600)
    # 后台 TDX 行情服务器测速任务的执行周期。
    tdxhub_bestip_refresh_seconds: float = Field(default=1800.0, gt=0, le=86400)
    sina_hq_page_workers: int = Field(default=4, ge=1, le=8)
    # 单次历史资金流备选查询的总 I/O 预算（包含连接、分页和逐日聚合）。
    tdxhub_fund_flow_timeout_seconds: float = Field(default=60.0, gt=0, le=90)

    eastmoney_min_interval_seconds: float = 1.0
    eastmoney_datacenter_min_interval_seconds: float = 1.0
    eastmoney_datacenter_cooldown_seconds: float = 10.0
    eastmoney_jitter_min_seconds: float = 0.1
    eastmoney_jitter_max_seconds: float = 0.5
    eastmoney_cooldown_seconds: float = 120.0
    eastmoney_transient_failure_threshold: int = 3
    # 公共出站代理：供按出口 IP 风控的上游接口统一使用（当前为东财 K 线与资金流）。
    # 各 provider 在代码里声明自己的 ProxyScope，未声明的接口一律保持直连。
    outbound_proxy_type: Literal["none", "http", "socks5"] = "none"
    outbound_proxy_url: str = ""
    outbound_proxy_timeout_seconds: float = Field(default=20.0, ge=5, le=120)
    outbound_proxy_retries: int = Field(default=2, ge=0, le=6)

    background_task_jitter_seconds: float = 15.0
    background_task_lease_seconds: float = 60.0
    background_task_standby_poll_seconds: float = 10.0
    background_task_readiness_failure_threshold: int = Field(default=3, ge=1, le=100)
    market_daily_bar_refresh_enabled: bool = True
    market_daily_bar_refresh_poll_seconds: int = Field(default=60, ge=15, le=3600)
    market_daily_bar_refresh_retry_base_seconds: int = Field(default=60, ge=1, le=1800)
    market_daily_observation_retention_days: int = Field(default=1095, ge=7, le=3650)
    market_daily_attempt_retention_days: int = Field(default=1095, ge=30, le=3650)
    workflow_job_poll_seconds: float = Field(default=0.5, gt=0)
    workflow_job_lease_seconds: int = Field(default=900, ge=30)
    workflow_job_max_attempts: int = Field(default=2, ge=1, le=5)
    workflow_job_retry_base_seconds: float = Field(default=5.0, ge=0)
    workflow_job_worker_concurrency: int = Field(default=2, ge=1, le=8)
    workflow_job_max_running_per_user: int = Field(default=1, ge=1, le=8)
    workflow_job_max_active_per_user: int = Field(default=10, ge=1, le=1000)
    workflow_job_max_active_total: int = Field(default=100, ge=1, le=10000)
    workflow_job_retention_seconds: int = Field(default=30 * 24 * 60 * 60, ge=3600)
    database_backup_enabled: bool = True
    database_backup_interval_seconds: int = Field(default=24 * 60 * 60, ge=300)
    database_backup_retention_count: int = Field(default=3, ge=1, le=90)
    database_backup_include_market_daily: bool = True
    market_daily_backup_interval_days: int = Field(default=7, ge=1, le=90)
    market_daily_backup_compression_level: int = Field(default=1, ge=1, le=9)
    database_backup_dir: Path | None = None
    database_backup_mirror_dir: Path | None = None

    notion_enabled: bool = False
    notion_api_token: str = ""
    notion_parent_page_id: str = ""
    notion_database_id: str = ""

    feishu_enabled: bool = True
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_folder_token: str = ""
    feishu_wiki_space_id: str = ""
    feishu_wiki_daily_review_parent: str = ""
    feishu_wiki_analysis_parent: str = ""
    feishu_daily_review_folder: str = ""
    feishu_analysis_folder: str = ""
    feishu_default_receiver: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""

    bot_enabled: bool = False
    bot_command_prefix: str = "/"
    bot_service_user_id: int = 0
    bot_feishu_app_id: str = ""
    bot_feishu_app_secret: str = ""
    bot_rate_limit_requests: int = 10
    bot_rate_limit_window: int = 60
    bot_webhook_max_skew_seconds: int = 300
    bot_event_dedup_ttl_seconds: int = 600
    bot_job_poll_seconds: float = 1.0
    bot_job_lease_seconds: int = 900
    bot_job_max_attempts: int = 3
    bot_job_retry_base_seconds: float = 5.0
    bot_job_worker_concurrency: int = 2
    bot_batch_concurrency: int = 2
    bot_batch_max_stocks: int = 10
    bot_admin_users: list[str] = Field(default_factory=list)

    iwencai_enabled: bool = False
    iwencai_base_url: str = "https://openapi.iwencai.com"
    iwencai_api_key: str = ""

    anysearch_api_key: str = Field(default="", repr=False)

    http_trust_env: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    web_fetch_max_response_bytes: int = Field(default=20 * 1024 * 1024, ge=64 * 1024, le=100 * 1024 * 1024)
    web_fetch_browser_enabled: bool = True
    web_fetch_browser_timeout_seconds: float = Field(default=20.0, ge=5.0, le=120.0)
    web_fetch_browser_settle_seconds: float = Field(default=10.0, ge=0.0, le=15.0)
    web_fetch_browser_max_concurrency: int = Field(default=2, ge=1, le=8)

    eastmoney_cookie: str = ""
    fred_api_key: str = ""
    baidu_cookie: str = ""
    baidu_acs_token: str = ""
    ths_cookie: str = ""
    legulegu_token: str = ""

    multi_agent_enabled: bool = True
    disabled_chat_skills: list[str] = Field(default_factory=list)
    disabled_chat_agents: list[str] = Field(default_factory=list)
    twitter_feeds: list[str] = Field(default_factory=lambda: ["qinbafrank"])
    twitter_post_retention_days: int = 90
    metrics_api_key: str = ""
    config_encryption_key: str = ""
    config_encryption_previous_keys: str = ""

    login_max_failures: int = 5
    login_window_seconds: int = 300
    login_lock_seconds: int = 300
    trust_proxy_headers: bool = False
    auth_cookie_secure: bool = False
    default_admin_username: str = "admin"
    default_admin_password: str = ""

    @property
    def llm(self) -> LLMSettingsView:
        from app.configuration.views import LLMSettingsView

        return LLMSettingsView.from_settings(self)

    @property
    def provider(self) -> ProviderSettingsView:
        from app.configuration.views import ProviderSettingsView

        return ProviderSettingsView.from_settings(self)

    @property
    def runtime(self) -> RuntimeSettingsView:
        from app.configuration.views import RuntimeSettingsView

        return RuntimeSettingsView.from_settings(self)

    @property
    def integrations(self) -> IntegrationSettingsView:
        from app.configuration.views import IntegrationSettingsView

        return IntegrationSettingsView.from_settings(self)

    @property
    def worker(self) -> WorkerSettingsView:
        from app.configuration.views import WorkerSettingsView

        return WorkerSettingsView.from_settings(self)

    @property
    def quant_strategy_hash_ledger_path(self) -> Path:
        return self.app_data_dir / "quant-strategy-hashes.json"

    @property
    def quant_strategy_publish_dir(self) -> Path:
        return self.app_data_dir / "quant-strategies-published"

    @model_validator(mode="after")
    def apply_provider_defaults(self) -> "Settings":
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
