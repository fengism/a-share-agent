"""每日复盘生成与历史记录应用服务。"""

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.daily_review import pipeline
from app.modules.daily_review.models import DailyReviewResult
from app.modules.daily_review.persistence import repository
from app.modules.daily_review.schemas import DailyReviewRequest


async def generate_daily_review(request: DailyReviewRequest, user_id: int) -> DailyReviewResult:
    return await pipeline.generate_daily_review(request, user_id)


def load_daily_review(date: str, user_id: int) -> DailyReviewResult | None:
    """同步读取复盘记录，供同步业务流程复用。"""
    return repository.load_daily_review(date, user_id)


async def get_daily_review_record(date: str, user_id: int) -> DailyReviewResult | None:
    return await call_blocking(
        repository.load_daily_review,
        date,
        user_id,
        semaphore=misc_semaphore,
    )


async def list_daily_review_history(
    user_id: int,
    *,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
) -> list[dict]:
    return await call_blocking(
        repository.list_daily_reviews,
        user_id,
        limit,
        offset,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )


async def remove_daily_review(date: str, user_id: int, *, can_delete_legacy: bool) -> bool:
    return await call_blocking(
        repository.delete_daily_review,
        date,
        user_id,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )
