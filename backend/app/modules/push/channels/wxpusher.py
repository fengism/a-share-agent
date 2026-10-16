"""微信服务号（WxPusher）通知通道。"""

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


class WxPusherChannel(NotificationChannel):
    """WxPusher 微信个人消息直达通道实现。"""

    @property
    def channel_id(self) -> str:
        return "wxpusher"

    @property
    def display_name(self) -> str:
        return "微信服务号 (WxPusher)"

    def is_configured(self, settings: Settings) -> bool:
        return bool(
            settings.wxpusher_app_token
            and settings.wxpusher_app_token.strip()
            and settings.wxpusher_uids
            and settings.wxpusher_uids.strip()
        )

    async def _post_message(
        self,
        app_token: str,
        uids: list[str],
        title: str,
        content_markdown: str,
    ) -> tuple[bool, str]:
        if not app_token or not uids:
            return False, "未配置 WxPusher appToken 或 uids"

        payload = {
            "appToken": app_token,
            "content": content_markdown,
            "summary": title[:100],
            "contentType": 3,  # 3 表示 Markdown 格式
            "uids": uids,
            "verifyPayType": 0,
        }

        try:
            response = await resilient_post(
                "https://wxpusher.zjiecode.com/api/send/message",
                json_data=payload,
                timeout=10.0,
            )
            if response.status_code != 200:
                return False, f"WxPusher 响应失败: HTTP {response.status_code}"
            res_data = response.json()
            if res_data.get("code") != 1000:
                return False, f"WxPusher 返回错误: {res_data.get('msg')}"
            return True, "微信服务号消息已发送"
        except Exception as exc:
            logger.warning("WxPusher 发送异常: %s", exc)
            return False, f"网络请求异常: {exc}"

    async def send(self, message: NotificationMessage, settings: Settings) -> ChannelSendResult:
        start_time = time.perf_counter()
        token = settings.wxpusher_app_token
        uids = [u.strip() for u in (settings.wxpusher_uids or "").split(",") if u.strip()]

        ok, msg = await self._post_message(token, uids, message.title, message.markdown_body)
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
        token = webhook_url or settings.wxpusher_app_token
        raw_uids = uids or settings.wxpusher_uids
        target_uids = [u.strip() for u in raw_uids.split(",") if u.strip()]
        if not token:
            return False, "请提供 WxPusher appToken"
        if not target_uids:
            return False, "请提供接收消息的 WxPusher UID"

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        test_md = f"""### 🎉 A-Share Agent 微信通道连通成功
> 发送时间：{now_str}
> 通道状态：**通信正常**

这是一条来自 **A-Share Agent** 的测试微信通知，系统后续将为您自动推送每日收盘复盘与题材雷达。
"""
        return await self._post_message(token, target_uids, "A-Share Agent 微信连通成功", test_md)
