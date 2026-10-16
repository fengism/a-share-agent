"""通用统一通知消息模型（Channel-Agnostic Notification Message）。

将具体的业务对象与外部通信通道（飞书、企微、微信服务号、钉钉等）解耦：
- 格式化器（Formatters）负责将业务事件转化为通用的 NotificationMessage。
- 通知通道（NotificationChannel）只消费 NotificationMessage，并将其渲染为特定平台的报文协议。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NotificationSeverity(str, Enum):
    """通知严重级别/重要度。"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ALERT = "alert"


class ChannelSendResult(BaseModel):
    """单个通知通道的发送结果。"""
    channel_id: str
    channel_name: str
    success: bool
    message: str
    elapsed_ms: float = 0.0


class NotificationMessage(BaseModel):
    """抽象通道无关的标准通知消息载荷。"""
    title: str
    summary: str = ""
    markdown_body: str
    fields: list[tuple[str, str]] = Field(default_factory=list)
    severity: NotificationSeverity = NotificationSeverity.INFO
    category: str = "general"
    card_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
