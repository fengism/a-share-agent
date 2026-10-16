"""飞书 Bot Command（事件订阅）配置分组。"""

from __future__ import annotations

from pydantic import Field

from app.configuration.groups.base import ConfigGroup


class BotGroup(ConfigGroup):
    """飞书 Bot 事件订阅、限流与任务队列。"""

    PREFIX = "bot_"

    bot_enabled: bool = False
    bot_command_prefix: str = "/"
    bot_service_user_id: int = 0
    # 已弃用：Bot 现复用 feishu_app_id / feishu_app_secret（见 Settings.apply_provider_defaults）。
    # 保留字段仅为兼容旧 .env / 旧数据库行；新部署无需配置。
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
