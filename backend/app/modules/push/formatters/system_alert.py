"""系统与异动告警通知格式化器。"""

from __future__ import annotations

from typing import Any

from app.modules.push.domain.message import NotificationMessage, NotificationSeverity


def format_system_alert(
    title: str,
    content_markdown: str,
    severity: NotificationSeverity = NotificationSeverity.WARNING,
    metadata: dict[str, Any] | None = None,
) -> NotificationMessage:
    """构建标准系统或行情异动通知消息。"""
    emoji_map = {
        NotificationSeverity.INFO: "ℹ️",
        NotificationSeverity.SUCCESS: "✅",
        NotificationSeverity.WARNING: "⚠️",
        NotificationSeverity.ALERT: "🚨",
    }
    emoji = emoji_map.get(severity, "🔔")
    full_title = f"{emoji} {title}"

    return NotificationMessage(
        title=full_title,
        summary=title[:100],
        markdown_body=content_markdown,
        severity=severity,
        category="system_alert",
        metadata=metadata or {},
    )
