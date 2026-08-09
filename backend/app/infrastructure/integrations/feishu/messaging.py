"""飞书消息发送能力。"""

import json

from app.infrastructure.integrations.feishu.transport import FeishuTransport

MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


class FeishuMessageClient:
    def __init__(self, transport: FeishuTransport) -> None:
        self._transport = transport

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
