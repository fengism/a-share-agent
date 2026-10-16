"""钉钉群机器人通知通道。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any

from app.configuration import get_effective_settings
from app.configuration.schema import Settings
from app.modules.push.channels.base import NotificationChannel
from app.modules.push.channels.http_client import resilient_post
from app.modules.push.domain.message import ChannelSendResult, NotificationMessage

logger = logging.getLogger(__name__)


def compute_dingtalk_sign(secret: str, timestamp: int) -> str:
    """计算钉钉自定义机器人的 HMAC-SHA256 签名并进行 URL 编码。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))


class DingTalkChannel(NotificationChannel):
    """钉钉群自定义 Webhook 机器人通道实现。"""

    @property
    def channel_id(self) -> str:
        return "dingtalk"

    @property
    def display_name(self) -> str:
        return "钉钉群机器人"

    def is_configured(self, settings: Settings) -> bool:
        return bool(settings.dingtalk_webhook_url and settings.dingtalk_webhook_url.strip())

    async def _post_markdown(
        self,
        webhook_url: str,
        title: str,
        markdown_text: str,
        secret: str = "",
    ) -> tuple[bool, str]:
        if not webhook_url:
            return False, "未配置钉钉 Webhook 地址"

        target_url = webhook_url
        if secret:
            ts = int(time.time() * 1000)
            sign = compute_dingtalk_sign(secret, ts)
            delimiter = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{delimiter}timestamp={ts}&sign={sign}"

        payload: dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {
                "title": title or "A股投资助手通知",
                "text": f"### {title}\n\n{markdown_text}" if title not in markdown_text else markdown_text,
            },
        }

        try:
            response = await resilient_post(
                target_url,
                json_data=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            if response.status_code != 200:
                return False, f"钉钉响应失败: HTTP {response.status_code} {response.text[:200]}"
            res_data = response.json()
            if res_data.get("errcode") != 0:
                return False, f"钉钉返回错误: {res_data.get('errmsg')} (errcode={res_data.get('errcode')})"
            return True, "钉钉消息已送达"
        except Exception as exc:
            logger.warning("钉钉 Webhook 发送异常: %s", exc)
            return False, f"网络请求异常: {exc}"

    async def send(self, message: NotificationMessage, settings: Settings) -> ChannelSendResult:
        start_time = time.perf_counter()
        url = settings.dingtalk_webhook_url
        secret = settings.dingtalk_webhook_secret

        ok, msg = await self._post_markdown(
            url,
            title=message.title,
            markdown_text=message.markdown_body,
            secret=secret,
        )
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
        url = webhook_url or settings.dingtalk_webhook_url
        sec = secret if secret != "" else settings.dingtalk_webhook_secret

        if not url:
            return False, "请填写钉钉 Webhook 地址"

        test_title = "【测试】A股智能投资助手通知连通性"
        test_content = (
            "### 🔔 钉钉群机器人连通性测试\n\n"
            "这是一条来自 **A-Share Agent** 的连通性验证消息。\n\n"
            "- **通道类型**: 钉钉自定义群机器人 (DingTalk)\n"
            "- **安全策略**: " + ("已开启 HMAC-SHA256 签名" if sec else "未开启加签") + "\n"
            "- **状态**: 正常连通\n\n"
            "> 恭喜！您已成功配置钉钉推送，收盘复盘与个股雷达将准时推送到此群。"
        )
        return await self._post_markdown(url, title=test_title, markdown_text=test_content, secret=sec)
