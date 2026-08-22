"""Bot 外部平台 Webhook 应用服务。"""

from collections.abc import Mapping

from app.configuration import get_settings
from app.core.metrics import metrics
from app.modules.bot.job_processor import enqueue_bot_message
from app.modules.bot.platforms.feishu import (
    FeishuBotConfigurationError,
    FeishuBotPayloadError,
    FeishuBotVerificationError,
)
from app.modules.bot.platforms.registry import feishu_platform
from app.modules.bot.schemas import FeishuWebhookPayload, FeishuWebhookResponse


class BotWebhookConfigurationError(RuntimeError):
    pass


class BotWebhookVerificationError(RuntimeError):
    pass


class BotWebhookPayloadError(ValueError):
    pass


async def process_feishu_webhook(
    payload: FeishuWebhookPayload,
    *,
    headers: Mapping[str, str],
    body: bytes,
) -> FeishuWebhookResponse:
    if not get_settings().bot_enabled:
        return FeishuWebhookResponse(code=0)
    try:
        decoded = feishu_platform.decode_payload(
            payload.model_dump(by_alias=True, exclude_none=True),
            headers=headers,
            body=body,
        )
        challenge = feishu_platform.challenge(decoded)
        if challenge is not None:
            return FeishuWebhookResponse(challenge=challenge)
        message = feishu_platform.parse_message(decoded)
    except FeishuBotConfigurationError as error:
        metrics.record_bot_event("configuration_failed")
        raise BotWebhookConfigurationError(str(error)) from error
    except FeishuBotVerificationError as error:
        metrics.record_bot_event("verification_failed")
        raise BotWebhookVerificationError from error
    except FeishuBotPayloadError as error:
        metrics.record_bot_event("invalid_payload")
        raise BotWebhookPayloadError(str(error)) from error

    if message is not None:
        await enqueue_bot_message(message)
    return FeishuWebhookResponse(code=0)
