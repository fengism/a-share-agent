"""Bot 模块对 HTTP 和 Runtime 适配器开放的稳定入口。"""

from app.modules.bot.admin_schemas import BotAdminJobItem, BotAdminJobsResponse, BotJobStatus
from app.modules.bot.admin_service import (
    BotJobNotFailedError,
    BotJobNotFoundError,
    BotJobStateChangedError,
    list_bot_admin_jobs,
    retry_bot_admin_job,
)
from app.modules.bot.job_processor import process_next_bot_job
from app.modules.bot.schemas import FeishuWebhookPayload, FeishuWebhookResponse
from app.modules.bot.webhook_service import (
    BotWebhookConfigurationError,
    BotWebhookPayloadError,
    BotWebhookVerificationError,
    process_feishu_webhook,
)

__all__ = [
    "BotAdminJobItem",
    "BotAdminJobsResponse",
    "BotJobNotFailedError",
    "BotJobNotFoundError",
    "BotJobStateChangedError",
    "BotJobStatus",
    "BotWebhookConfigurationError",
    "BotWebhookPayloadError",
    "BotWebhookVerificationError",
    "FeishuWebhookPayload",
    "FeishuWebhookResponse",
    "list_bot_admin_jobs",
    "process_next_bot_job",
    "process_feishu_webhook",
    "retry_bot_admin_job",
]
