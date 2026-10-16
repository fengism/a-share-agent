"""飞书自定义群机器人通知通道。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.configuration import get_effective_settings
from app.configuration.schema import Settings
from app.modules.push.channels.base import NotificationChannel
from app.modules.push.channels.http_client import resilient_post
from app.modules.push.domain.message import ChannelSendResult, NotificationMessage, NotificationSeverity

logger = logging.getLogger(__name__)


def compute_feishu_sign(secret: str, timestamp: int) -> str:
    """计算飞书自定义机器人的 HMAC-SHA256 签名。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


class FeishuChannel(NotificationChannel):
    """飞书群自定义 Webhook 机器人通道实现。"""

    @property
    def channel_id(self) -> str:
        return "feishu"

    @property
    def display_name(self) -> str:
        return "飞书群机器人"

    def is_configured(self, settings: Settings) -> bool:
        return bool(settings.feishu_webhook_url and settings.feishu_webhook_url.strip())

    async def _post_payload(self, webhook_url: str, card_or_text: dict, secret: str = "") -> tuple[bool, str]:
        if not webhook_url:
            return False, "未配置飞书 Webhook 地址"

        payload: dict[str, Any] = {}
        if secret:
            ts = int(time.time())
            payload["timestamp"] = str(ts)
            payload["sign"] = compute_feishu_sign(secret, ts)

        if "elements" in card_or_text or "header" in card_or_text:
            payload["msg_type"] = "interactive"
            payload["card"] = card_or_text
        else:
            payload.update(card_or_text)

        try:
            response = await resilient_post(webhook_url, json_data=payload, timeout=10.0)
            if response.status_code != 200:
                return False, f"飞书响应失败: HTTP {response.status_code} {response.text[:200]}"
            res_data = response.json()
            if res_data.get("code") != 0 and res_data.get("StatusCode") != 0:
                return False, f"飞书返回错误: {res_data.get('msg') or res_data.get('StatusMessage')}"
            return True, "飞书消息已送达"
        except Exception as exc:
            logger.warning("飞书 Webhook 发送异常: %s", exc)
            return False, f"网络请求异常: {exc}"

    def _render_card_from_message(self, message: NotificationMessage) -> dict[str, Any]:
        """将通用 NotificationMessage 渲染为飞书交互式卡片。"""
        if message.card_data:
            return message.card_data

        template_map = {
            NotificationSeverity.INFO: "blue",
            NotificationSeverity.SUCCESS: "green",
            NotificationSeverity.WARNING: "orange",
            NotificationSeverity.ALERT: "red",
        }
        color = template_map.get(message.severity, "blue")

        elements: list[dict[str, Any]] = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": message.markdown_body,
                },
            }
        ]

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": message.title},
                "template": color,
            },
            "elements": elements,
        }

    async def send(self, message: NotificationMessage, settings: Settings) -> ChannelSendResult:
        start_time = time.perf_counter()
        url = settings.feishu_webhook_url
        secret = settings.feishu_webhook_secret

        card = self._render_card_from_message(message)
        ok, msg = await self._post_payload(url, card, secret=secret)
        elapsed = (time.perf_counter() - start_time) * 1000

        return ChannelSendResult(
            channel_id=self.channel_id,
            channel_name=self.display_name,
            success=ok,
            message=msg,
            elapsed_ms=round(elapsed, 2),
        )

    async def send_test(
        self,
        webhook_url: str = "",
        secret: str = "",
        uids: str = "",
    ) -> tuple[bool, str]:
        settings = get_effective_settings()
        url = webhook_url or settings.feishu_webhook_url
        sec = secret or settings.feishu_webhook_secret
        if not url:
            return False, "请填写飞书 Webhook 地址"

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        test_card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🎉 A-Share Agent 飞书通道连通成功"},
                "template": "green",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"您好！这是一条来自 **A-Share Agent** 的测试通知。\n\n"
                                   f"• 发送时间：`{now_str}`\n"
                                   f"• 通道状态：**通信正常**\n\n"
                                   f"系统后续将在此群为您自动推送每日收盘复盘、题材挖掘雷达与异动预警。",
                    },
                }
            ],
        }
        return await self._post_payload(url, test_card, secret=sec)
