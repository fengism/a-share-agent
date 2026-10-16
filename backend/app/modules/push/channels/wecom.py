"""企业微信群机器人通知通道。"""

from __future__ import annotations

import logging
import time

import httpx

from app.configuration import get_effective_settings
from app.configuration.schema import Settings
from app.modules.push.channels.base import NotificationChannel
from app.modules.push.domain.message import ChannelSendResult, NotificationMessage

from app.modules.push.channels.http_client import resilient_post

logger = logging.getLogger(__name__)


class WecomChannel(NotificationChannel):
    """企业微信群自定义 Webhook 机器人通道实现。"""

    @property
    def channel_id(self) -> str:
        return "wecom"

    @property
    def display_name(self) -> str:
        return "企业微信群机器人"

    def is_configured(self, settings: Settings) -> bool:
        return bool(settings.wecom_webhook_url and settings.wecom_webhook_url.strip())

    async def _post_markdown(self, webhook_url: str, markdown_text: str) -> tuple[bool, str]:
        if not webhook_url:
            return False, "未配置企业微信 Webhook 地址"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_text,
            },
        }

        try:
            response = await resilient_post(webhook_url, json_data=payload, timeout=10.0)
            if response.status_code != 200:
                return False, f"企业微信响应失败: HTTP {response.status_code} {response.text[:200]}"
            res_data = response.json()
            if res_data.get("errcode") != 0:
                return False, f"企业微信返回错误: {res_data.get('errmsg')}"
            return True, "企业微信消息已送达"
        except Exception as exc:
            logger.warning("企业微信 Webhook 发送异常: %s", exc)
            return False, f"网络请求异常: {exc}"

    async def send(self, message: NotificationMessage, settings: Settings) -> ChannelSendResult:
        start_time = time.perf_counter()
        url = settings.wecom_webhook_url

        ok, msg = await self._post_markdown(url, message.markdown_body)
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
        url = webhook_url or settings.wecom_webhook_url
        if not url:
            return False, "请填写企业微信 Webhook 地址"

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        test_md = f"""### 🎉 A-Share Agent 企业微信通道连通成功
> 发送时间：<font color="comment">{now_str}</font>
> 通道状态：<font color="info">通信正常</font>

这是一条来自 **A-Share Agent** 的测试通知，系统后续将在此群为您自动推送每日收盘复盘与题材雷达。
"""
        return await self._post_markdown(url, test_md)
