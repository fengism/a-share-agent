"""自动推送分发调度中枢。

基于通道策略模式（Channel Strategy）与统一通知模型（NotificationMessage），
提供松耦合、可插拔的多通道消息分发与向下兼容接口。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.configuration import get_effective_settings
from app.modules.daily_review.models import DailyReviewResult
from app.modules.potential.schemas import PotentialDailyResult
from app.modules.push.channels.dingtalk import DingTalkChannel, compute_dingtalk_sign
from app.modules.push.channels.feishu import FeishuChannel, compute_feishu_sign
from app.modules.push.channels.registry import channel_registry
from app.modules.push.channels.wecom import WecomChannel
from app.modules.push.channels.wxpusher import WxPusherChannel
from app.modules.push.domain.message import ChannelSendResult, NotificationMessage
from app.modules.push.formatters.daily_review import (
    daily_review_formatter,
    format_daily_review_feishu_card,
    format_daily_review_wecom_markdown,
)
from app.modules.push.formatters.potential_stocks import (
    format_potential_stocks_feishu_card,
    format_potential_stocks_wecom_markdown,
    potential_stocks_formatter,
)

logger = logging.getLogger(__name__)

# 单独实例供兼容层直接调用辅助方法
_feishu_channel = FeishuChannel()
_dingtalk_channel = DingTalkChannel()
_wecom_channel = WecomChannel()
_wxpusher_channel = WxPusherChannel()


async def send_feishu_webhook(webhook_url: str, card_or_text: dict, secret: str = "") -> tuple[bool, str]:
    """向飞书群机器人发送卡片或富文本消息（兼容函数）。"""
    return await _feishu_channel._post_payload(webhook_url, card_or_text, secret=secret)


async def send_dingtalk_webhook(
    webhook_url: str,
    title: str,
    markdown_text: str,
    secret: str = "",
) -> tuple[bool, str]:
    """向钉钉群机器人发送 Markdown 消息（兼容函数）。"""
    return await _dingtalk_channel._post_markdown(webhook_url, title, markdown_text, secret=secret)


async def send_wecom_webhook(webhook_url: str, markdown_text: str) -> tuple[bool, str]:
    """向企业微信群机器人发送 Markdown 消息（兼容函数）。"""
    return await _wecom_channel._post_markdown(webhook_url, markdown_text)


async def send_wxpusher(
    app_token: str,
    uids: list[str],
    title: str,
    content_markdown: str,
) -> tuple[bool, str]:
    """向微信服务号 WxPusher 推送消息（兼容函数）。"""
    return await _wxpusher_channel._post_message(app_token, uids, title, content_markdown)


_recent_dispatches: dict[str, float] = {}
_DEBOUNCE_WINDOW_SECONDS = 180  # 3 分钟内同一事件同一日期防抖
# 防抖表只增不减：每发生一次「新事件×新日期」就留一条永久记录。写入时顺带清理
# 过期项（而不是靠进程重启），否则长跑进程会一直攒着历史上所有的键。
_DEBOUNCE_PURGE_INTERVAL_SECONDS = 600.0
_last_debounce_purge = 0.0


def _prune_recent_dispatches(now: float) -> None:
    """删除已过防抖窗口的键（调用方负责保证串行）。"""
    global _last_debounce_purge
    if now - _last_debounce_purge < _DEBOUNCE_PURGE_INTERVAL_SECONDS:
        return
    _last_debounce_purge = now
    deadline = now - _DEBOUNCE_WINDOW_SECONDS
    for key in [k for k, seen_at in _recent_dispatches.items() if seen_at <= deadline]:
        del _recent_dispatches[key]


async def dispatch_notification(message: NotificationMessage, *, force: bool = False) -> dict[str, str]:
    """核心分发函数：将通用通知消息并发推送至当前所有已启用的活跃通道。"""
    settings = get_effective_settings()
    if not settings.push_auto_enabled:
        logger.info("自动推送总开关未启用，跳过推送 category=%s", message.category)
        return {}

    # 按类别检查开关
    if message.category == "daily_review" and not settings.push_daily_review_auto:
        logger.info("每日复盘自动推送未启用，跳过推送")
        return {}
    if message.category == "potential_stocks" and not settings.push_potential_auto:
        logger.info("潜力股自动推送未启用，跳过推送")
        return {}

    # 防抖校验：同一类别同一日期在短期内避免重复打扰
    date_key = message.metadata.get("date")
    debounce_key = f"{message.category}:{date_key}" if date_key else ""
    now = time.time()
    if not force and debounce_key and debounce_key in _recent_dispatches:
        if now - _recent_dispatches[debounce_key] < _DEBOUNCE_WINDOW_SECONDS:
            logger.info("触发通知防抖机制，跳过重复投递: key=%s", debounce_key)
            return {"debounce": "已防抖跳过"}

    active_channels = channel_registry.get_active(settings, category=message.category)
    if not active_channels:
        logger.info("未检测到有效配置的推送通道，跳过推送 category=%s", message.category)
        return {}

    results: dict[str, str] = {}
    history_channel_details: dict[str, dict[str, Any]] = {}

    async def _send_to_channel(channel) -> tuple[str, ChannelSendResult]:
        try:
            res = await channel.send(message, settings)
            return channel.channel_id, res
        except Exception as exc:
            logger.warning("通道推送异常 channel=%s error=%s", channel.channel_id, exc)
            return channel.channel_id, ChannelSendResult(
                channel_id=channel.channel_id,
                channel_name=channel.display_name,
                success=False,
                message=f"发送异常: {exc}",
            )

    send_tasks = [_send_to_channel(ch) for ch in active_channels]
    executed = await asyncio.gather(*send_tasks)

    for ch_id, send_result in executed:
        status_text = "成功" if send_result.success else f"失败: {send_result.message}"
        results[ch_id] = status_text
        history_channel_details[ch_id] = {
            "name": send_result.channel_name,
            "success": send_result.success,
            "message": send_result.message,
            "elapsed_ms": send_result.elapsed_ms,
        }
        logger.info(
            "通道推送完成: channel=%s success=%s elapsed_ms=%.1f msg=%s",
            ch_id,
            send_result.success,
            send_result.elapsed_ms,
            send_result.message,
        )

    if debounce_key:
        _prune_recent_dispatches(now)
        _recent_dispatches[debounce_key] = now

    # 异步落库审计历史
    try:
        from app.infrastructure.persistence.notification_history import record_notification_delivery

        record_notification_delivery(
            category=message.category,
            title=message.title,
            summary=message.summary,
            severity=message.severity.value if hasattr(message.severity, "value") else str(message.severity),
            channels=history_channel_details,
            metadata=message.metadata,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("记录通知审计历史失败: %s", exc)

    return results


async def dispatch_daily_review_notification(review: DailyReviewResult) -> dict[str, str]:
    """将每日复盘结果推送至所有启用的通知通道。"""
    msg = daily_review_formatter.format(review)
    return await dispatch_notification(msg)


async def dispatch_potential_stocks_notification(result: PotentialDailyResult) -> dict[str, str]:
    """将潜力股与题材雷达结果推送至所有启用的通知通道。"""
    msg = potential_stocks_formatter.format(result)
    return await dispatch_notification(msg)


async def send_test_notification(
    channel: str,
    webhook_url: str = "",
    secret: str = "",
    uids: str = "",
) -> tuple[bool, str]:
    """向指定通道发送测试验证消息。"""
    target_channel = channel_registry.get(channel)
    if target_channel is None:
        return False, f"不支持的通知通道: {channel}"

    return await target_channel.send_test(
        webhook_url=webhook_url,
        secret=secret,
        uids=uids,
    )


__all__ = [
    "compute_dingtalk_sign",
    "compute_feishu_sign",
    "dispatch_daily_review_notification",
    "dispatch_notification",
    "dispatch_potential_stocks_notification",
    "format_daily_review_feishu_card",
    "format_daily_review_wecom_markdown",
    "format_potential_stocks_feishu_card",
    "format_potential_stocks_wecom_markdown",
    "send_dingtalk_webhook",
    "send_feishu_webhook",
    "send_test_notification",
    "send_wecom_webhook",
    "send_wxpusher",
]
