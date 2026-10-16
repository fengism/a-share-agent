"""通知通道注册中心（Channel Registry）。

统一维护系统已安装的通知通道，支持动态扩展新通道，实现开箱即用的插件化管理。
"""

from __future__ import annotations

from app.configuration.schema import Settings
from app.modules.push.channels.base import NotificationChannel
from app.modules.push.channels.dingtalk import DingTalkChannel
from app.modules.push.channels.feishu import FeishuChannel
from app.modules.push.channels.wecom import WecomChannel
from app.modules.push.channels.wxpusher import WxPusherChannel


class ChannelRegistry:
    """通道注册中心。"""

    def __init__(self) -> None:
        self._channels: dict[str, NotificationChannel] = {}

    def register(self, channel: NotificationChannel) -> None:
        """注册新通道。"""
        self._channels[channel.channel_id] = channel

    def get(self, channel_id: str) -> NotificationChannel | None:
        """根据 ID 获取通道实例。"""
        return self._channels.get(channel_id)

    def list_all(self) -> list[NotificationChannel]:
        """列出所有已注册通道。"""
        return list(self._channels.values())

    def get_active(self, settings: Settings, category: str | None = None) -> list[NotificationChannel]:
        """获取当前配置下所有已启用且配置完整的通道，支持按通知类别过滤订阅。"""
        channels = [c for c in self._channels.values() if c.is_enabled(settings)]
        if category:
            channels = [c for c in channels if c.is_subscribed(category, settings)]
        return channels


def create_default_registry() -> ChannelRegistry:
    """创建并初始化包含默认通道的注册中心。"""
    reg = ChannelRegistry()
    reg.register(FeishuChannel())
    reg.register(DingTalkChannel())
    reg.register(WecomChannel())
    reg.register(WxPusherChannel())
    return reg


# 全局默认单例
channel_registry = create_default_registry()
