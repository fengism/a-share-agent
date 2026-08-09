"""Bot 外部平台 Webhook 路由。"""

from fastapi import APIRouter, Request

from app.api.errors import ApiError, BadRequestError
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

router = APIRouter()


@router.post(
    "/feishu",
    response_model=FeishuWebhookResponse,
    response_model_exclude_none=True,
)
async def feishu_webhook(
    payload: FeishuWebhookPayload,
    request: Request,
) -> FeishuWebhookResponse:
    settings = get_settings()
    if not settings.bot_enabled:
        return FeishuWebhookResponse(code=0)
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise BadRequestError("飞书事件请求体过大", code="bot.payload_too_large")
    try:
        decoded = feishu_platform.decode_payload(
            payload.model_dump(by_alias=True, exclude_none=True),
            headers=request.headers,
            body=body,
        )
        challenge = feishu_platform.challenge(decoded)
        if challenge is not None:
            return FeishuWebhookResponse(challenge=challenge)
        message = feishu_platform.parse_message(decoded)
    except FeishuBotConfigurationError as exc:
        metrics.record_bot_event("configuration_failed")
        raise ApiError(
            status_code=503,
            code="bot.feishu_not_configured",
            message=str(exc),
        ) from exc
    except FeishuBotVerificationError as exc:
        metrics.record_bot_event("verification_failed")
        raise ApiError(
            status_code=403,
            code="bot.feishu_verification_failed",
            message="飞书事件校验失败",
        ) from exc
    except FeishuBotPayloadError as exc:
        metrics.record_bot_event("invalid_payload")
        raise BadRequestError(str(exc), code="bot.invalid_payload") from exc

    if message is None:
        return FeishuWebhookResponse(code=0)
    await enqueue_bot_message(message)
    return FeishuWebhookResponse(code=0)
