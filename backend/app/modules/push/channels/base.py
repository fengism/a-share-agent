"""通知通道抽象基类（Strategy Pattern）。

每个通信通道只需实现此接口，即可天然接入通知总线，满足开闭原则（OCP）：
- channel_id: 唯一标识（feishu, wecom, wxpusher, dingtalk 等）
- display_name: 展示名称
- is_configured: 检查当前全局配置中该通道是否已启用且配置完整
- send: 发送标准 NotificationMessage
- send_test: 发送连通性测试消息
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.configuration.schema import Settings
from app.modules.push.domain.message import ChannelSendResult, NotificationMessage


class NotificationChannel(ABC):
    """通知通道抽象基类。"""

    @property
    @abstractmethod
    def channel_id(self) -> str:
        """通道唯一英文标识符。"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """通道中文展示名称。"""
        pass

    @abstractmethod
    def is_configured(self, settings: Settings) -> bool:
        """检查通道在当前配置中是否有效配置。"""
        pass

    def is_enabled(self, settings: Settings) -> bool:
        """检查通道在当前配置中是否开启且有效配置。
        
        支持通过独立通道开关（如 push_feishu_enabled 等）临时禁用通道而无需抹除密钥。
        """
        attr_name = f"push_{self.channel_id}_enabled"
        channel_switch = getattr(settings, attr_name, True)
        return bool(channel_switch) and self.is_configured(settings)

    def is_subscribed(self, category: str, settings: Settings) -> bool:
        """检查该通道是否订阅指定类别的通知。默认订阅全部。"""
        return True

    @abstractmethod
    async def send(self, message: NotificationMessage, settings: Settings) -> ChannelSendResult:
        """向该通道发送标准通知。"""
        pass

    @abstractmethod
    async def send_test(
        self,
        webhook_url: str = "",
        secret: str = "",
        uids: str = "",
    ) -> tuple[bool, str]:
        """向该通道发送连通性测试消息。"""
        pass
