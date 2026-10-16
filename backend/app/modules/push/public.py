"""Push 模块对 HTTP 和其他业务适配器开放的稳定入口。"""

from app.modules.push.application import execute_push_request
from app.modules.push.channels import DingTalkChannel, NotificationChannel, channel_registry
from app.modules.push.dispatcher import (
    compute_dingtalk_sign,
    compute_feishu_sign,
    dispatch_daily_review_notification,
    dispatch_notification,
    dispatch_potential_stocks_notification,
    format_daily_review_feishu_card,
    format_daily_review_wecom_markdown,
    format_potential_stocks_feishu_card,
    format_potential_stocks_wecom_markdown,
    send_dingtalk_webhook,
    send_feishu_webhook,
    send_test_notification,
    send_wecom_webhook,
    send_wxpusher,
)
from app.modules.push.domain import ChannelSendResult, NotificationMessage, NotificationSeverity
from app.modules.push.formatters.system_alert import format_system_alert
from app.modules.push.schemas import (
    NotificationChannelStatus,
    PushRequest,
    PushResponse,
    TestWebhookRequest,
    TestWebhookResponse,
)
from app.modules.push.service import PushIntegrationNotConfiguredError
from app.modules.push.subscribers import register_push_subscribers

__all__ = [
    "ChannelSendResult",
    "DingTalkChannel",
    "NotificationChannel",
    "NotificationChannelStatus",
    "NotificationMessage",
    "NotificationSeverity",
    "PushIntegrationNotConfiguredError",
    "PushRequest",
    "PushResponse",
    "TestWebhookRequest",
    "TestWebhookResponse",
    "channel_registry",
    "compute_dingtalk_sign",
    "compute_feishu_sign",
    "dispatch_daily_review_notification",
    "dispatch_notification",
    "dispatch_potential_stocks_notification",
    "execute_push_request",
    "format_daily_review_feishu_card",
    "format_daily_review_wecom_markdown",
    "format_potential_stocks_feishu_card",
    "format_potential_stocks_wecom_markdown",
    "format_system_alert",
    "register_push_subscribers",
    "send_dingtalk_webhook",
    "send_feishu_webhook",
    "send_test_notification",
    "send_wecom_webhook",
    "send_wxpusher",
]
