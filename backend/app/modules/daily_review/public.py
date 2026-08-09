"""Daily Review 模块对其他业务模块开放的稳定入口。"""

from app.modules.daily_review import pipeline as daily_review_pipeline
from app.modules.daily_review.models import DailyReviewResult, DailyReviewSection
from app.modules.daily_review.persistence.repository import load_daily_review
from app.modules.daily_review.schemas import DailyReviewRequest


async def generate_daily_review(request: DailyReviewRequest, user_id: int) -> DailyReviewResult:
    return await daily_review_pipeline.generate_daily_review(request, user_id)

__all__ = [
    "DailyReviewRequest",
    "DailyReviewResult",
    "DailyReviewSection",
    "generate_daily_review",
    "load_daily_review",
]
