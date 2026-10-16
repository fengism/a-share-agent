"""Daily Review 模块对其他业务模块开放的稳定入口。"""

from app.modules.daily_review.models import CycleTrend, DailyReviewResult, DailyReviewSection
from app.modules.daily_review.pdf_service import (
    generate_daily_review_pdf_html,
    render_daily_review_pdf_bytes,
)
from app.modules.daily_review.pipeline import prewarm_daily_review
from app.modules.daily_review.schemas import DailyReviewHistoryItem, DailyReviewRequest
from app.modules.daily_review.service import (
    generate_daily_review,
    get_cycle_trend,
    get_daily_review_record,
    list_daily_review_history,
    load_daily_review,
    remove_daily_review,
)

__all__ = [
    "CycleTrend",
    "DailyReviewHistoryItem",
    "DailyReviewRequest",
    "DailyReviewResult",
    "DailyReviewSection",
    "generate_daily_review",
    "generate_daily_review_pdf_html",
    "get_cycle_trend",
    "get_daily_review_record",
    "list_daily_review_history",
    "load_daily_review",
    "prewarm_daily_review",
    "remove_daily_review",
    "render_daily_review_pdf_bytes",
]
