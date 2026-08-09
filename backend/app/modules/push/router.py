import logging

from fastapi import APIRouter, Depends

from app.api.errors import ApiError, BadRequestError, NotFoundError
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.errors import log_internal_error
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.push.schemas import PushRequest, PushResponse
from app.modules.push.service import PushIntegrationNotConfiguredError, execute_push

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
        return await call_blocking(
            execute_push,
            request,
            user["id"],
            semaphore=misc_semaphore,
        )
    except ValueError as exc:
        raise BadRequestError(str(exc), code="push.invalid_request") from exc
    except LookupError as exc:
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
