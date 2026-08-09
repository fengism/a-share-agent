"""Bot 管理员任务查询与重试接口。"""

from fastapi import APIRouter, Depends, Query

from app.api.errors import ConflictError, NotFoundError
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.metrics import metrics
from app.modules.auth.public import AuthenticatedUser, require_admin
from app.modules.bot.admin_schemas import BotAdminJobItem, BotAdminJobsResponse, BotJobStatus
from app.modules.bot.persistence import jobs as job_store

router = APIRouter()


def _to_item(job: job_store.BotJob) -> BotAdminJobItem:
    return BotAdminJobItem(
        id=job.id,
        event_id=job.event_id,
        platform=job.platform,
        request_user_id=job.request_user_id,
        command_name=job.command_name,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.get("/jobs", response_model=BotAdminJobsResponse)
async def list_bot_jobs(
    status: BotJobStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    admin: AuthenticatedUser = Depends(require_admin),
) -> BotAdminJobsResponse:
    jobs = await call_blocking(
        job_store.list_jobs,
        status=status,
        limit=limit,
        semaphore=database_semaphore,
    )
    counts = await call_blocking(
        job_store.count_jobs_by_status,
        semaphore=database_semaphore,
    )
    return BotAdminJobsResponse(counts=counts, jobs=[_to_item(job) for job in jobs])


@router.post("/jobs/{job_id}/retry", response_model=BotAdminJobItem)
async def retry_bot_job(
    job_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
) -> BotAdminJobItem:
    job = await call_blocking(job_store.get_job, job_id, semaphore=database_semaphore)
    if job is None:
        raise NotFoundError("Bot 任务不存在", code="bot.job_not_found")
    if job.status != "failed":
        raise ConflictError("仅失败任务可以重试", code="bot.job_not_failed")
    retried = await call_blocking(
        job_store.retry_failed,
        job_id,
        semaphore=database_semaphore,
    )
    if not retried:
        raise ConflictError("任务状态已变化，请刷新后重试", code="bot.job_state_changed")
    metrics.record_bot_event("manual_retry")
    updated = await call_blocking(job_store.get_job, job_id, semaphore=database_semaphore)
    if updated is None:
        raise NotFoundError("Bot 任务不存在", code="bot.job_not_found")
    return _to_item(updated)
