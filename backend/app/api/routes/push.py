"""内容推送 HTTP API。"""

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.auth.dependencies import require_active_user
from app.api.errors import ApiError, BadRequestError, NotFoundError
from app.core.errors import log_internal_error
from app.core.exceptions import ResourceNotFoundError
from app.domain.identity import AuthenticatedUser
from app.modules.push.public import (
    NotificationChannelStatus,
    PushIntegrationNotConfiguredError,
    PushRequest,
    PushResponse,
    TestWebhookRequest,
    TestWebhookResponse,
    execute_push_request,
    send_test_notification,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=PushResponse)
async def push_content(request: PushRequest, user: AuthenticatedUser = Depends(require_active_user)):
    """将分析结果、复盘或聊天内容推送到 Notion 或飞书。

    Param:
        request: PushRequest 请求体，包含 target、type、receiver 及内容字段。
    Return:
        PushResponse: 推送结果，含目标、文档 URL、标题和提示信息。
    """
    try:
        return await execute_push_request(request, user["id"])
    except ValueError as exc:
        raise BadRequestError(str(exc), code="push.invalid_request") from exc
    except (LookupError, ResourceNotFoundError) as exc:
        raise NotFoundError(str(exc), code="push.content_not_found") from exc
    except PushIntegrationNotConfiguredError as exc:
        raise BadRequestError(str(exc), code="push.integration_not_configured") from exc
    except Exception as exc:
        error_id, detail = log_internal_error(
            logger,
            f"推送内容 target={request.target} type={request.type}",
            exc,
            "推送服务暂时不可用，请稍后重试",
        )
        raise ApiError(
            status_code=502,
            code="push.upstream_unavailable",
            message=detail,
            headers={"X-Error-ID": error_id},
        ) from exc


@router.post("/test-webhook", response_model=TestWebhookResponse)
async def trigger_channel_test_webhook(
    request: TestWebhookRequest,
    _user: AuthenticatedUser = Depends(require_active_user),
):
    """测试指定通道（飞书、企业微信、微信）的通知连通性。"""
    ok, msg = await send_test_notification(
        channel=request.channel,
        webhook_url=request.webhook_url,
        secret=request.secret,
        uids=request.uids,
    )
    return TestWebhookResponse(success=ok, channel=request.channel, message=msg)


@router.get("/channels", response_model=NotificationChannelStatus)
async def get_notification_channel_status(
    _user: AuthenticatedUser = Depends(require_active_user),
):
    """获取当前已配置的自动推送与通知通道状态。"""
    from app.configuration import get_effective_settings

    settings = get_effective_settings()
    return NotificationChannelStatus(
        feishu_configured=bool(settings.feishu_webhook_url),
        dingtalk_configured=bool(settings.dingtalk_webhook_url),
        wecom_configured=bool(settings.wecom_webhook_url),
        wxpusher_configured=bool(settings.wxpusher_app_token and settings.wxpusher_uids),
        feishu_enabled=settings.push_feishu_enabled,
        dingtalk_enabled=settings.push_dingtalk_enabled,
        wecom_enabled=settings.push_wecom_enabled,
        wxpusher_enabled=settings.push_wxpusher_enabled,
        auto_enabled=settings.push_auto_enabled,
        daily_review_auto=settings.push_daily_review_auto,
        potential_auto=settings.push_potential_auto,
    )


@router.get("/history", response_model=list[dict[str, Any]])
async def get_notification_history(
    limit: int = 50,
    _user: AuthenticatedUser = Depends(require_active_user),
):
    """获取最近的通知推送历史审计日志。"""
    from app.infrastructure.persistence.notification_history import load_notification_history

    records = load_notification_history(limit=limit)
    return [r.model_dump(mode="json") for r in records]


@router.delete("/history")
async def clear_notification_history_records(
    _user: AuthenticatedUser = Depends(require_active_user),
) -> dict[str, bool]:
    """清空通知推送历史审计日志。"""
    from app.infrastructure.persistence.notification_history import clear_notification_history

    success = clear_notification_history()
    return {"success": success}
