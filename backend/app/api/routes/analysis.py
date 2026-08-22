"""AI 分析历史与执行 HTTP 路由聚合入口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_active_user
from app.api.errors import NotFoundError
from app.api.routes import analysis_execution
from app.api.schemas import DeleteResponse
from app.domain.identity import AuthenticatedUser
from app.modules.analysis.public import (
    AnalysisHistoryItem,
    AnalysisResult,
    list_all_analysis_history,
    list_analysis_history,
    load_analysis_history,
    remove_analysis_history,
)

router = APIRouter()


@router.get("/history/all", response_model=list[AnalysisHistoryItem])
async def get_all_analysis_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """获取所有股票的历史 AI 分析记录列表。

    Return:
        list[AnalysisHistoryItem]: 全部历史分析条目集合。
    """
    return await list_all_analysis_history(
        user["id"],
        limit=limit,
        offset=offset,
        can_delete_legacy=bool(user["is_admin"]),
    )


router.include_router(analysis_execution.router)


@router.get("/{code}/history", response_model=list[AnalysisHistoryItem])
async def get_analysis_history(
    code: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """读取指定股票的历史分析索引列表。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[AnalysisHistoryItem]: 按日期排序的历史分析摘要条目。
    """
    return await list_analysis_history(
        code,
        user["id"],
        limit=limit,
        offset=offset,
        can_delete_legacy=bool(user["is_admin"]),
    )


@router.get("/{code}/history/{date}", response_model=AnalysisResult)
async def get_analysis_by_date(code: str, date: str, user: AuthenticatedUser = Depends(require_active_user)):
    """读取指定股票在指定日期的分析结果，命中缓存优先。

    Param:
        code: 股票代码（路径参数），6 位数字。
        date: 分析日期（路径参数），格式 YYYYMMDD。
    Return:
        AnalysisResult: 该日的完整分析结果；若不存在则返回 404。
    """
    result = await load_analysis_history(code, date, user["id"])
    if result is None:
        raise NotFoundError(
            f"未找到 {code} 在 {date} 的分析记录",
            code="analysis.history_not_found",
        )
    return result


@router.delete("/{code}/history/{date}", response_model=DeleteResponse)
async def delete_analysis_history(
    code: str,
    date: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> DeleteResponse:
    deleted = await remove_analysis_history(
        code,
        date,
        user["id"],
        can_delete_legacy=bool(user["is_admin"]),
    )
    if not deleted:
        raise NotFoundError("分析记录不存在", code="analysis.history_not_found")
    return DeleteResponse()
