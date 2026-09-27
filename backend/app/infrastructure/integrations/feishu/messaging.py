"""飞书消息发送能力。"""

import json

from app.infrastructure.integrations.feishu.transport import FeishuTransport

MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
IMAGE_UPLOAD_URL = "https://open.feishu.cn/open-apis/im/v1/images"


class FeishuMessageClient:
    def __init__(self, transport: FeishuTransport) -> None:
        self._transport = transport

    def upload_image(self, image_bytes: bytes, *, filename: str = "chart.png", timeout: int = 30) -> str:
        """上传图片换取 image_key，供消息卡片引用。"""
        self._transport.auth.validate_settings()
        data = self._transport.post_multipart(
            IMAGE_UPLOAD_URL,
            data={"image_type": "message"},
            files={"image": (filename, image_bytes, "image/png")},
            error_prefix="飞书图片上传失败",
            timeout=timeout,
        )
        return data["data"]["image_key"]

    def send_card(self, receiver: str, card: dict) -> None:
        self._transport.auth.validate_settings()
        receive_id_type = "chat_id" if receiver.startswith("oc_") else "open_id"
        self._transport.post_json(
            MESSAGE_URL,
            {
                "receive_id": receiver,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
            "飞书消息发送失败",
            params={"receive_id_type": receive_id_type},
        )
