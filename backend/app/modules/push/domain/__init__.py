"""推送领域模型。"""

from app.modules.push.domain.message import (
    ChannelSendResult,
    NotificationMessage,
    NotificationSeverity,
)

__all__ = [
    "ChannelSendResult",
    "NotificationMessage",
    "NotificationSeverity",
]
