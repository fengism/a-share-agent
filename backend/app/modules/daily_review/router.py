from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.errors import NotFoundError
from app.contracts.common import DeleteResponse
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.daily_review.models import DailyReviewResult
from app.modules.daily_review.persistence.repository import delete_daily_review, list_daily_reviews, load_daily_review
from app.modules.daily_review.pipeline import generate_daily_review
from app.modules.daily_review.schemas import DailyReviewHistoryItem, DailyReviewRequest

router = APIRouter()


@router.post("/generate", response_model=DailyReviewResult)
async def generate_review(request: DailyReviewRequest, user: AuthenticatedUser = Depends(require_active_user)):
    """触发生成指定日期的每日市场复盘。"""
    return await generate_daily_review(request, user["id"])


@router.get("/history", response_model=list[DailyReviewHistoryItem])
async def get_daily_review_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """获取已生成的每日复盘历史索引。"""
    return await call_blocking(
        list_daily_reviews,
        user["id"],
        limit,
        offset,
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
    )


@router.get("/{date}", response_model=DailyReviewResult)
async def get_daily_review(date: str, user: AuthenticatedUser = Depends(require_active_user)):
    """读取指定日期的复盘详情。

    Param:
        date: 日期字符串（路径参数），如 YYYY-MM-DD。
    Return:
        DailyReviewResult: 该日的完整复盘结果；若不存在则返回 404。
    """
    review = await call_blocking(
        load_daily_review,
        date,
        user["id"],
        semaphore=misc_semaphore,
    )
    if review is None:
        raise NotFoundError("复盘记录不存在", code="daily_review.not_found")
    return review


@router.delete("/{date}", response_model=DeleteResponse)
async def delete_review(
    date: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> DeleteResponse:
    deleted = await call_blocking(
        delete_daily_review,
        date,
        user["id"],
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
    )
    if not deleted:
        raise NotFoundError("复盘记录不存在", code="daily_review.not_found")
    return DeleteResponse()
