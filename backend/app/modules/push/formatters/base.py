"""消息格式化器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.modules.push.domain.message import NotificationMessage

PayloadT = TypeVar("PayloadT")


class NotificationFormatter(ABC, Generic[PayloadT]):
    """将业务载荷转化为标准通知消息的格式化器。"""

    @abstractmethod
    def format(self, payload: PayloadT) -> NotificationMessage:
        """格式化为 NotificationMessage。"""
        pass
