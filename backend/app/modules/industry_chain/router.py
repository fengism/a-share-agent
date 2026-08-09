from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.api.errors import ConflictError, NotFoundError
from app.api.streaming import SSE_RESPONSES
from app.contracts.common import DeleteResponse
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.industry_chain import stream as industry_chain_stream
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.persistence.repository import (
    delete_industry_chain,
    list_industry_chains,
    load_industry_chain,
)
from app.modules.industry_chain.schemas import IndustryChainHistoryItem, IndustryChainLatestResponse

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
    return await call_blocking(
        list_industry_chains,
        user["id"],
        name or None,
        limit,
        offset,
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
    )


@router.get("/{name}/latest", response_model=IndustryChainLatestResponse)
async def get_industry_chain_latest(name: str, user: AuthenticatedUser = Depends(require_active_user)):
    """获取指定产业链的最新存档（按时间倒序第一条）。

    Param:
        name: 产业链名称（路径参数）
    Return:
        dict: 包含 archive_id；不存在时返回空
    """
    items = await call_blocking(
        list_industry_chains,
        user["id"],
        name,
        1,
        0,
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
    )
    if not items:
        return {"archive_id": ""}
    return {"archive_id": items[0].archive_id, "saved_at": items[0].saved_at}


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
    result = await call_blocking(
        load_industry_chain,
        name,
        archive_id,
        user["id"],
        semaphore=misc_semaphore,
    )
    if result is None:
        raise NotFoundError("产业链存档不存在", code="industry_chain.archive_not_found")
    return result


@router.delete("/{name}/archive/{archive_id}", response_model=DeleteResponse)
async def delete_industry_chain_archive(
    name: str,
    archive_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> DeleteResponse:
    deleted = await call_blocking(
        delete_industry_chain,
        name,
        archive_id,
        user["id"],
        bool(user["is_admin"]),
        semaphore=misc_semaphore,
    )
    if not deleted:
        raise NotFoundError("产业链存档不存在", code="industry_chain.archive_not_found")
    return DeleteResponse()


@router.get("/{name}/stream", response_class=EventSourceResponse, responses=SSE_RESPONSES)
async def stream_industry_chain(name: str, user: AuthenticatedUser = Depends(require_active_user)):
    """SSE 端点，流式推送产业链分析进度。

    Param:
        name: 产业链名称（路径参数）；同名并发请求会返回 409。
    Return:
        EventSourceResponse: SSE 流，逐条推送 IndustryChainProgress 事件。
    """

    try:
        event_generator = await industry_chain_stream.create_industry_chain_event_generator(name, user["id"])
    except industry_chain_stream.IndustryChainAlreadyRunningError as exc:
        raise ConflictError(str(exc), code="industry_chain.already_running") from exc

    return EventSourceResponse(event_generator)
