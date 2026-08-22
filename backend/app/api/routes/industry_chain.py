"""产业链分析 HTTP API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.api.auth.dependencies import require_active_user
from app.api.errors import NotFoundError, TooManyRequestsError
from app.api.schemas import DeleteResponse
from app.api.streaming import SSE_RESPONSES
from app.domain.identity import AuthenticatedUser
from app.modules.industry_chain.public import (
    IndustryChainHistoryItem,
    IndustryChainLatestResponse,
    IndustryChainResult,
    WorkflowCapacityError,
    create_industry_chain_event_generator,
    get_latest_industry_chain_archive,
    list_industry_chain_history,
    load_industry_chain_archive,
    remove_industry_chain_archive,
)

router = APIRouter()


@router.get("/history", response_model=list[IndustryChainHistoryItem])
async def get_industry_chain_history(
    name: str = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """获取产业链分析历史索引（按名称可选过滤）。

    Param:
        name: 可选名称过滤（query 参数）
    Return:
        list[IndustryChainHistoryItem]: 历史条目摘要列表，按时间倒序
    """
    return await list_industry_chain_history(
        user["id"],
        name=name or None,
        limit=limit,
        offset=offset,
        can_delete_legacy=bool(user["is_admin"]),
    )


@router.get("/{name}/latest", response_model=IndustryChainLatestResponse)
async def get_industry_chain_latest(name: str, user: AuthenticatedUser = Depends(require_active_user)):
    """获取指定产业链的最新存档（按时间倒序第一条）。

    Param:
        name: 产业链名称（路径参数）
    Return:
        dict: 包含 archive_id；不存在时返回空
    """
    return await get_latest_industry_chain_archive(
        name,
        user["id"],
        can_delete_legacy=bool(user["is_admin"]),
    )


@router.get("/{name}/archive/{archive_id}", response_model=IndustryChainResult)
async def get_industry_chain_archive(
    name: str,
    archive_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """按名称与存档 ID 加载历史产业链分析结果。

    Param:
        name: 产业链名称（路径参数）
        archive_id: 存档 ID（路径参数）
    Return:
        IndustryChainResult: 完整的产业链分析结果
    """
    result = await load_industry_chain_archive(name, archive_id, user["id"])
    if result is None:
        raise NotFoundError("产业链存档不存在", code="industry_chain.archive_not_found")
    return result


@router.delete("/{name}/archive/{archive_id}", response_model=DeleteResponse)
async def delete_industry_chain_archive(
    name: str,
    archive_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> DeleteResponse:
    deleted = await remove_industry_chain_archive(
        name,
        archive_id,
        user["id"],
        can_delete_legacy=bool(user["is_admin"]),
    )
    if not deleted:
        raise NotFoundError("产业链存档不存在", code="industry_chain.archive_not_found")
    return DeleteResponse()


@router.get("/{name}/stream", response_class=EventSourceResponse, responses=SSE_RESPONSES)
async def stream_industry_chain(name: str, user: AuthenticatedUser = Depends(require_active_user)):
    """SSE 端点，流式推送产业链分析进度。

    Param:
        name: 产业链名称（路径参数）；同名并发请求会附着到已有任务。
    Return:
        EventSourceResponse: SSE 流，逐条推送 IndustryChainProgress 事件。
    """

    try:
        event_generator = await create_industry_chain_event_generator(name, user["id"])
    except WorkflowCapacityError as error:
        raise TooManyRequestsError(
            "产业链任务队列已满，请等待已有任务完成",
            code=f"workflow.{error.scope}_capacity_reached",
            retry_after_seconds=30,
        ) from error
    return EventSourceResponse(event_generator)
