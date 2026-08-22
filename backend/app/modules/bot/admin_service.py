"""Bot 管理任务应用服务。"""

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.metrics import metrics
from app.modules.bot.admin_schemas import BotAdminJobItem, BotAdminJobsResponse, BotJobStatus
from app.modules.bot.persistence import jobs as job_store


class BotJobNotFoundError(LookupError):
    pass


class BotJobNotFailedError(RuntimeError):
    pass


class BotJobStateChangedError(RuntimeError):
    pass


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


async def list_bot_admin_jobs(
    *,
    status: BotJobStatus | None,
    limit: int,
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


async def retry_bot_admin_job(job_id: str) -> BotAdminJobItem:
    job = await call_blocking(job_store.get_job, job_id, semaphore=database_semaphore)
    if job is None:
        raise BotJobNotFoundError
    if job.status != "failed":
        raise BotJobNotFailedError
    retried = await call_blocking(
        job_store.retry_failed,
        job_id,
        semaphore=database_semaphore,
    )
    if not retried:
        raise BotJobStateChangedError
    metrics.record_bot_event("manual_retry")
    updated = await call_blocking(job_store.get_job, job_id, semaphore=database_semaphore)
    if updated is None:
        raise BotJobNotFoundError
    return _to_item(updated)
