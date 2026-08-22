"""Bot 外部平台 Webhook HTTP 路由。"""

from fastapi import APIRouter, Request

from app.api.errors import ApiError, BadRequestError
from app.modules.bot.public import (
    BotWebhookConfigurationError,
    BotWebhookPayloadError,
    BotWebhookVerificationError,
    FeishuWebhookPayload,
    FeishuWebhookResponse,
    process_feishu_webhook,
)

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
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise BadRequestError("飞书事件请求体过大", code="bot.payload_too_large")
    try:
        return await process_feishu_webhook(
            payload,
            headers=request.headers,
            body=body,
        )
    except BotWebhookConfigurationError as exc:
        raise ApiError(
            status_code=503,
            code="bot.feishu_not_configured",
            message=str(exc),
        ) from exc
    except BotWebhookVerificationError as exc:
        raise ApiError(
            status_code=403,
            code="bot.feishu_verification_failed",
            message="飞书事件校验失败",
        ) from exc
    except BotWebhookPayloadError as exc:
        raise BadRequestError(str(exc), code="bot.invalid_payload") from exc
