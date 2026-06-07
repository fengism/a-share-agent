from fastapi import APIRouter, HTTPException

from app.models.daily_review import DailyReviewHistoryItem, DailyReviewRequest, DailyReviewResult
from app.services.daily_review.pipeline import generate_daily_review
from app.services.daily_review.storage import list_daily_reviews, load_daily_review

router = APIRouter()


@router.post("/generate", response_model=DailyReviewResult)
async def generate_review(request: DailyReviewRequest):
    """触发生成指定日期的每日市场复盘。

    Param:
        request: DailyReviewRequest 请求体，包含目标日期等参数。
    Return:
        DailyReviewResult: 生成完成的结构化复盘内容。
    """
    try:
        return await generate_daily_review(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成每日复盘失败: {e}")


@router.get("/history", response_model=list[DailyReviewHistoryItem])
async def get_daily_review_history():
    """获取已生成的每日复盘历史索引。

    Return:
        list[DailyReviewHistoryItem]: 历史复盘条目摘要列表。
    """
    try:
        return list_daily_reviews()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取复盘历史失败: {e}")


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
