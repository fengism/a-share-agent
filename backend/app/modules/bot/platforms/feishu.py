"""飞书事件订阅适配器。"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hmac import compare_digest
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.configuration.schema import Settings
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.domain.content import ContentBlock
from app.infrastructure.integrations.feishu.adapter import to_feishu_card
from app.infrastructure.integrations.feishu.client import FeishuClient, feishu_client
from app.modules.bot.models import BotMessage, BotResponse
from app.modules.bot.platforms.base import BotPlatform


class FeishuBotConfigurationError(Exception):
    pass


class FeishuBotVerificationError(Exception):
    pass


class FeishuBotPayloadError(Exception):
    pass


class FeishuPlatform(BotPlatform):
    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        *,
        clock: Callable[[], float] = time.time,
        client: FeishuClient = feishu_client,
    ) -> None:
        self._settings_provider = settings_provider
        self._clock = clock
        self._client = client

    @property
    def platform_name(self) -> str:
        return "feishu"

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        normalized_name = name.lower()
        return next(
            (value for key, value in headers.items() if key.lower() == normalized_name),
            "",
        )

    def _verify_signature(self, headers: Mapping[str, str], body: bytes) -> None:
        settings = self._settings_provider()
        encrypt_key = settings.feishu_encrypt_key.strip()
        if not encrypt_key:
            return
        timestamp = self._header(headers, "x-lark-request-timestamp")
        nonce = self._header(headers, "x-lark-request-nonce")
        signature = self._header(headers, "x-lark-signature")
        if not timestamp or not nonce or not signature:
            raise FeishuBotVerificationError("飞书请求签名头缺失")
        try:
            request_time = int(timestamp)
        except ValueError as exc:
            raise FeishuBotVerificationError("飞书请求时间戳无效") from exc
        max_skew_seconds = max(1, settings.bot_webhook_max_skew_seconds)
        if abs(self._clock() - request_time) > max_skew_seconds:
            raise FeishuBotVerificationError("飞书请求时间戳已过期")
        expected = hashlib.sha256(
            timestamp.encode("utf-8") + nonce.encode("utf-8") + encrypt_key.encode("utf-8") + body
        ).hexdigest()
        if not compare_digest(signature, expected):
            raise FeishuBotVerificationError("飞书请求签名无效")

    def _decrypt_payload(self, encrypted: str) -> dict[str, Any]:
        encrypt_key = self._settings_provider().feishu_encrypt_key.strip()
        if not encrypt_key:
            raise FeishuBotConfigurationError("FEISHU_ENCRYPT_KEY 未配置")
        try:
            encrypted_bytes = base64.b64decode(encrypted, validate=True)
            if len(encrypted_bytes) <= 16:
                raise ValueError("encrypted payload is too short")
            key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
            decryptor = Cipher(
                algorithms.AES(key),
                modes.CBC(encrypted_bytes[:16]),
            ).decryptor()
            padded = decryptor.update(encrypted_bytes[16:]) + decryptor.finalize()
            unpadder = PKCS7(algorithms.AES.block_size).unpadder()
            plaintext = unpadder.update(padded) + unpadder.finalize()
            payload = json.loads(plaintext.decode("utf-8"))
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FeishuBotVerificationError("飞书加密事件解密失败") from exc
        if not isinstance(payload, dict):
            raise FeishuBotPayloadError("飞书事件内容不是对象")
        return payload

    def decode_payload(
        self,
        payload: dict[str, Any],
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> dict[str, Any]:
        self._verify_signature(headers, body)
        decoded = self._decrypt_payload(payload["encrypt"]) if payload.get("encrypt") else payload
        verification_token = self._settings_provider().feishu_verification_token.strip()
        if not verification_token:
            raise FeishuBotConfigurationError("FEISHU_VERIFICATION_TOKEN 未配置")
        header = decoded.get("header") if isinstance(decoded.get("header"), dict) else {}
        token = str(decoded.get("token") or header.get("token") or "")
        if not token or not compare_digest(token, verification_token):
            raise FeishuBotVerificationError("飞书 Verification Token 无效")
        return decoded

    @staticmethod
    def challenge(payload: dict[str, Any]) -> str | None:
        challenge = payload.get("challenge")
        if payload.get("type") == "url_verification" and isinstance(challenge, str):
            return challenge
        return None

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        raw_content = message.get("content")
        if not isinstance(raw_content, str):
            return ""
        try:
            content = json.loads(raw_content)
        except json.JSONDecodeError:
            return ""
        text = content.get("text") if isinstance(content, dict) else None
        return text.strip() if isinstance(text, str) else ""

    @staticmethod
    def _timestamp(raw_timestamp: Any) -> datetime:
        try:
            return datetime.fromtimestamp(int(raw_timestamp) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return datetime.now(timezone.utc)

    def parse_message(self, payload: dict[str, Any]) -> BotMessage | None:
        header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
        if header.get("event_type") != "im.message.receive_v1":
            return None
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        if message.get("message_type") != "text":
            return None
        text = self._message_text(message)
        if not text:
            return None
        mentions = message.get("mentions") if isinstance(message.get("mentions"), list) else []
        for mention in mentions:
            if isinstance(mention, dict) and isinstance(mention.get("key"), str):
                text = text.replace(mention["key"], " ")
        text = " ".join(text.split())
        chat_type = "private" if message.get("chat_type") == "p2p" else "group"
        if chat_type == "group" and not mentions:
            return None

        sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
        sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), dict) else {}
        user_id = str(sender_id.get("open_id") or sender_id.get("union_id") or sender_id.get("user_id") or "")
        if not user_id:
            raise FeishuBotPayloadError("飞书事件缺少发送者 ID")
        message_id = str(message.get("message_id") or "")
        event_id = str(header.get("event_id") or message_id)
        chat_id = str(message.get("chat_id") or user_id)
        return BotMessage(
            platform=self.platform_name,
            message_id=message_id,
            event_id=event_id,
            user_id=user_id,
            user_name=str(sender.get("sender_type") or "飞书用户"),
            chat_id=chat_id,
            chat_type=chat_type,
            content=text,
            mentioned=bool(mentions),
            timestamp=self._timestamp(message.get("create_time") or header.get("create_time")),
            raw_data=payload,
        )

    async def send_response(self, message: BotMessage, response: BotResponse) -> None:
        card = to_feishu_card(
            "chat",
            response.title,
            [ContentBlock(type="paragraph", text=response.text)],
            "",
        )
        await call_blocking(
            self._client.send_card,
            message.chat_id or message.user_id,
            card,
            semaphore=misc_semaphore,
        )
