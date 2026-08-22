"""Bot 管理员任务查询与重试 HTTP 接口。"""

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_admin
from app.api.errors import ConflictError, NotFoundError
from app.domain.identity import AuthenticatedUser
from app.modules.bot.public import (
    BotAdminJobItem,
    BotAdminJobsResponse,
    BotJobNotFailedError,
    BotJobNotFoundError,
    BotJobStateChangedError,
    BotJobStatus,
    list_bot_admin_jobs,
    retry_bot_admin_job,
)

router = APIRouter()


@router.get("/jobs", response_model=BotAdminJobsResponse)
async def list_bot_jobs(
    status: BotJobStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    admin: AuthenticatedUser = Depends(require_admin),
) -> BotAdminJobsResponse:
    return await list_bot_admin_jobs(
        status=status,
        limit=limit,
    )


@router.post("/jobs/{job_id}/retry", response_model=BotAdminJobItem)
async def retry_bot_job(
    job_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
) -> BotAdminJobItem:
    try:
        return await retry_bot_admin_job(job_id)
    except BotJobNotFoundError as error:
        raise NotFoundError("Bot 任务不存在", code="bot.job_not_found") from error
    except BotJobNotFailedError as error:
        raise ConflictError("仅失败任务可以重试", code="bot.job_not_failed") from error
    except BotJobStateChangedError as error:
        raise ConflictError("任务状态已变化，请刷新后重试", code="bot.job_state_changed") from error
