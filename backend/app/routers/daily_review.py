from fastapi import APIRouter, HTTPException

from app.models.daily_review import DailyReviewHistoryItem, DailyReviewRequest, DailyReviewResult
from app.services.daily_review.pipeline import generate_daily_review
from app.services.daily_review.storage import list_daily_reviews, load_daily_review

router = APIRouter()


@router.post("/generate", response_model=DailyReviewResult)
async def generate_review(request: DailyReviewRequest):
    try:
        return await generate_daily_review(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成每日复盘失败: {e}")


@router.get("/history", response_model=list[DailyReviewHistoryItem])
async def get_daily_review_history():
    try:
        return list_daily_reviews()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取复盘历史失败: {e}")


@router.get("/{date}", response_model=DailyReviewResult)
async def get_daily_review(date: str):
    review = load_daily_review(date)
    if review is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return review
