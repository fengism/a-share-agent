"""每日复盘 HTTP API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_active_user
from app.api.errors import BadRequestError, NotFoundError
from app.api.schemas import DeleteResponse
from app.domain.identity import AuthenticatedUser
from app.modules.daily_review.public import (
    DailyReviewHistoryItem,
    DailyReviewRequest,
    DailyReviewResult,
    generate_daily_review,
    get_daily_review_record,
    list_daily_review_history,
    remove_daily_review,
)

router = APIRouter()


@router.post("/generate", response_model=DailyReviewResult)
async def generate_review(request: DailyReviewRequest, user: AuthenticatedUser = Depends(require_active_user)):
    """触发生成指定日期的每日市场复盘。"""
    try:
        return await generate_daily_review(request, user["id"])
    except ValueError as error:
        raise BadRequestError(str(error), code="daily_review.invalid_date") from error


@router.get("/history", response_model=list[DailyReviewHistoryItem])
async def get_daily_review_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """获取已生成的每日复盘历史索引。"""
    return await list_daily_review_history(
        user["id"],
        limit=limit,
        offset=offset,
        can_delete_legacy=bool(user["is_admin"]),
    )


@router.get("/{date}", response_model=DailyReviewResult)
async def get_daily_review(date: str, user: AuthenticatedUser = Depends(require_active_user)):
    """读取指定日期的复盘详情。

    Param:
        date: 日期字符串（路径参数），如 YYYY-MM-DD。
    Return:
        DailyReviewResult: 该日的完整复盘结果；若不存在则返回 404。
    """
    review = await get_daily_review_record(date, user["id"])
    if review is None:
        raise NotFoundError("复盘记录不存在", code="daily_review.not_found")
    return review


@router.delete("/{date}", response_model=DeleteResponse)
async def delete_review(
    date: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> DeleteResponse:
    deleted = await remove_daily_review(
        date,
        user["id"],
        can_delete_legacy=bool(user["is_admin"]),
    )
    if not deleted:
        raise NotFoundError("复盘记录不存在", code="daily_review.not_found")
    return DeleteResponse()
