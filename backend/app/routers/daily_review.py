from fastapi import APIRouter, HTTPException
import logging

from app.routers.errors import run_endpoint

from app.models.daily_review import DailyReviewHistoryItem, DailyReviewRequest, DailyReviewResult
from app.services.daily_review.pipeline import generate_daily_review
from app.services.daily_review.storage import list_daily_reviews, load_daily_review

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=DailyReviewResult)
async def generate_review(request: DailyReviewRequest):
    """触发生成指定日期的每日市场复盘。"""
    return await run_endpoint("生成每日复盘", lambda: generate_daily_review(request))


@router.get("/history", response_model=list[DailyReviewHistoryItem])
async def get_daily_review_history():
    """获取已生成的每日复盘历史索引。"""
    try:
        reviews = list_daily_reviews()
        return reviews
    except Exception as exc:
        logger.error("获取复盘历史失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取复盘历史失败: {exc}") from exc


@router.get("/{date}", response_model=DailyReviewResult)
async def get_daily_review(date: str):
    """读取指定日期的复盘详情。

    Param:
        date: 日期字符串（路径参数），如 YYYY-MM-DD。
    Return:
        DailyReviewResult: 该日的完整复盘结果；若不存在则返回 404。
    """
    review = load_daily_review(date)
    if review is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return review
