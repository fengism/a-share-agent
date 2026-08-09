"""AI 分析历史路由与执行路由聚合入口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.errors import NotFoundError
from app.configuration import get_effective_settings
from app.contracts.common import DeleteResponse
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.analysis import execution_router as analysis_execution
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence.repository import (
    delete_analysis,
    list_all_analyses,
    list_analyses,
)
from app.modules.analysis.persistence.repository import (
    get_analysis_by_date as get_analysis_by_date_service,
)
from app.modules.analysis.schemas import AnalysisHistoryItem
from app.modules.auth.public import AuthenticatedUser, require_active_user

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
    return await call_blocking(
        list_all_analyses,
        user["id"],
        limit,
        offset,
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
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
    return await call_blocking(
        list_analyses,
        code,
        user["id"],
        limit,
        offset,
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
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
    result = await call_blocking(
        get_analysis_by_date_service,
        code,
        date,
        user["id"],
        cache_ttl=get_effective_settings().cache_ttl_analysis,
        semaphore=misc_semaphore,
    )
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
    deleted = await call_blocking(
        delete_analysis,
        code,
        date,
        user["id"],
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
    )
    if not deleted:
        raise NotFoundError("分析记录不存在", code="analysis.history_not_found")
    return DeleteResponse()
