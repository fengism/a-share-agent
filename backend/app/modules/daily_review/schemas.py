"""每日复盘 HTTP 请求与列表响应模型。"""

from pydantic import BaseModel

from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewResult,
    DailyReviewSection,
)

__all__ = [
    "DailyReviewDataSnapshot",
    "DailyReviewHistoryItem",
    "DailyReviewRequest",
    "DailyReviewResult",
    "DailyReviewSection",
]


class DailyReviewRequest(BaseModel):
    """Purpose: 每日复盘接口的请求参数。"""
    date: str | None = None
    force: bool = False


class DailyReviewHistoryItem(BaseModel):
    """Purpose: 每日复盘历史列表的单条摘要。"""
    date: str
    title: str
    generated_at: str
    market_summary: str
    can_delete: bool
