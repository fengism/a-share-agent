"""每日复盘 HTTP API。"""

import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response

from app.api.auth.dependencies import require_active_user
from app.api.errors import BadRequestError, NotFoundError, ServiceUnavailableError
from app.api.schemas import DeleteResponse
from app.core.exceptions import UpstreamUnavailableError
from app.domain.identity import AuthenticatedUser
from app.modules.daily_review.public import (
    DailyReviewHistoryItem,
    DailyReviewRequest,
    DailyReviewResult,
    generate_daily_review,
    generate_daily_review_pdf_html,
    get_daily_review_record,
    list_daily_review_history,
    remove_daily_review,
    render_daily_review_pdf_bytes,
)

logger = logging.getLogger(__name__)

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


@router.get("/{date}/export-pdf")
async def export_daily_review_pdf(
    date: str,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """根据日期读取复盘记录，并生成包含矢量图表的 PDF。"""
    review = await get_daily_review_record(date, user["id"])
    if review is None:
        raise NotFoundError("复盘记录不存在", code="daily_review.not_found")

    html_content = generate_daily_review_pdf_html(review)
    try:
        pdf_bytes = await render_daily_review_pdf_bytes(html_content)
    except UpstreamUnavailableError:
        raise
    except Exception as exc:
        logger.exception("导出复盘 PDF 失败: date=%s", date)
        raise ServiceUnavailableError(
            "PDF 导出服务暂时不可用，请稍后重试",
            code="daily_review.pdf_export_failed",
        ) from exc
    filename = f"每日复盘_{review.date}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
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
