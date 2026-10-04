from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.auth.dependencies import require_active_user, require_admin
from app.api.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    TooManyRequestsError,
)
from app.api.schemas import DeleteResponse
from app.api.streaming import SSE_RESPONSES
from app.domain.identity import AuthenticatedUser
from app.modules.industry_chain.atlas import (
    AtlasBatchMineResponse,
    AtlasCatalog,
    AtlasChain,
    AtlasGraph,
    AtlasImportError,
    batch_mine_atlas_chains,
    build_atlas_catalog,
    build_atlas_graph,
    delete_imported_chain,
    get_atlas_chain,
    import_atlas_chains,
    mine_and_save_atlas_chain,
)
from app.modules.industry_chain.public import (
    IndustryChainHistoryItem,
    IndustryChainLatestResponse,
    IndustryChainResult,
    WorkflowCapacityError,
    create_industry_chain_event_generator,
    generate_industry_chain_pdf_html,
    get_latest_industry_chain_archive,
    list_industry_chain_history,
    load_industry_chain_archive,
    remove_industry_chain_archive,
    render_industry_chain_pdf_bytes,
)

router = APIRouter()

# 批量挖掘单次扫描的历史存档上限，避免管理员误触把全部存档读入内存
_BATCH_MINE_SCAN_LIMIT = 200


@router.post("/export-pdf")
async def export_custom_industry_chain_pdf(
    result: IndustryChainResult,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """基于前端传入的实时产业链分析结果对象直接生成纯矢量投研 PDF。"""
    html_content = generate_industry_chain_pdf_html(result)
    pdf_bytes = await render_industry_chain_pdf_bytes(html_content)

    name = result.name or "产业链"
    report_date = datetime.now().strftime("%Y%m%d")
    filename = f"{name}_产业链深度研究报告_{report_date}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/{name}/export-pdf")
async def export_industry_chain_pdf(
    name: str,
    archive_id: Annotated[str | None, Query()] = None,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """根据产业链名称与存档 ID，直接生成纯矢量投研 PDF 并下载。"""
    if archive_id:
        result = await load_industry_chain_archive(name, archive_id, user["id"])
    else:
        latest = await get_latest_industry_chain_archive(
            name, user["id"], can_delete_legacy=bool(user["is_admin"])
        )
        if latest is None or not latest.archive_id:
            result = None
        else:
            result = await load_industry_chain_archive(name, latest.archive_id, user["id"])

    if result is None:
        raise NotFoundError(
            f"未找到 {name} 产业链的分析存档，请先执行分析后再导出",
            code="industry_chain.archive_not_found",
        )

    html_content = generate_industry_chain_pdf_html(result)
    pdf_bytes = await render_industry_chain_pdf_bytes(html_content)

    chain_name = result.name or name
    report_date = datetime.now().strftime("%Y%m%d")
    filename = f"{chain_name}_产业链深度研究报告_{report_date}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/atlas/chains", response_model=AtlasCatalog)
async def get_industry_chain_atlas_catalog(
    user: AuthenticatedUser = Depends(require_active_user),
) -> AtlasCatalog:
    """产业链知识库目录：分类、链条摘要与规模统计。"""
    return build_atlas_catalog()


@router.get("/atlas/chains/{slug}", response_model=AtlasChain)
async def get_industry_chain_atlas_chain(
    slug: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> AtlasChain:
    """按 slug 获取单条产业链的上/中/下游完整图谱。"""
    chain = get_atlas_chain(slug)
    if chain is None:
        raise NotFoundError(f"产业链知识库中不存在: {slug}")
    return chain


class AtlasImportRequest(BaseModel):
    """外部导入产业链：YAML 或 JSON 文本，支持单条 / 数组 / {chains: [...]}。"""

    content: str = Field(min_length=1)
    overwrite: bool = False


class AtlasMineRequest(BaseModel):
    """从已存档的 AI 分析结果挖掘知识库条目。"""

    name: str = Field(min_length=1)
    archive_id: str = ""


@router.get("/atlas/graph", response_model=AtlasGraph)
async def get_industry_chain_atlas_graph(
    chains: Annotated[str | None, Query()] = None,
    user: AuthenticatedUser = Depends(require_active_user),
) -> AtlasGraph:
    """跨链全局产业链图谱；chains 传逗号分隔 slug 时只统计这些链。"""
    slugs = [item.strip() for item in chains.split(",") if item.strip()] if chains else None
    return build_atlas_graph(slugs)


@router.post("/atlas/mine", response_model=AtlasChain)
async def mine_industry_chain_atlas(
    request: AtlasMineRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> AtlasChain:
    """把指定存档（或该链最新存档）的分析结果挖掘进知识库并返回条目（管理员）。"""
    archive_id = request.archive_id
    if not archive_id:
        latest = await get_latest_industry_chain_archive(
            request.name, admin["id"], can_delete_legacy=True,
        )
        archive_id = (latest.archive_id or "") if latest is not None else ""
    if not archive_id:
        raise NotFoundError(f"没有可挖掘的产业链分析存档: {request.name}")
    result = await load_industry_chain_archive(request.name, archive_id, admin["id"])
    if result is None:
        raise NotFoundError("产业链存档不存在")
    if result.quality_status != "complete":
        raise BadRequestError("该存档未通过质量门（降级报告），不允许挖掘入库")
    chain = await mine_and_save_atlas_chain(result)
    if chain is None:
        raise BadRequestError("分析结果可挖掘内容不足（至少 2 个环节、3 家公司），未入库")
    return chain


@router.post("/atlas/mine-batch", response_model=AtlasBatchMineResponse)
async def batch_mine_industry_chain_atlas(
    admin: AuthenticatedUser = Depends(require_admin),
) -> AtlasBatchMineResponse:
    """批量挖掘历史产业链存档（管理员）。

    逐条加载存档并挖掘，未通过质量门或内容不足的存档计入 skipped 而非中断整批。
    """
    items = await list_industry_chain_history(
        admin["id"], name=None, limit=_BATCH_MINE_SCAN_LIMIT, offset=0, can_delete_legacy=True,
    )
    targets: list[tuple[str, IndustryChainResult]] = []
    skipped = 0
    for item in items:
        result = await load_industry_chain_archive(item.name, item.archive_id, admin["id"])
        if result is None:
            skipped += 1
            continue
        if result.quality_status != "complete":
            skipped += 1
            continue
        targets.append((item.name, result))

    response = await batch_mine_atlas_chains(targets)
    response.skipped += skipped
    return response


@router.post("/atlas/import", response_model=list[AtlasChain])
async def import_industry_chain_atlas(
    request: AtlasImportRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> list[AtlasChain]:
    """导入外部产业链定义（管理员），校验通过后写入导入目录并立即生效。"""
    try:
        return import_atlas_chains(request.content, overwrite=request.overwrite)
    except AtlasImportError as exc:
        message = str(exc)
        if "已存在" in message:
            raise ConflictError(message) from exc
        raise BadRequestError(message) from exc


@router.delete("/atlas/chains/{slug}", response_model=DeleteResponse)
async def delete_industry_chain_atlas_import(
    slug: str,
    admin: AuthenticatedUser = Depends(require_admin),
) -> DeleteResponse:
    """删除一条外部导入的产业链（管理员）；内置链条不可删除。"""
    if get_atlas_chain(slug) is None:
        raise NotFoundError(f"产业链知识库中不存在: {slug}")
    if not delete_imported_chain(slug):
        raise BadRequestError(f"内置产业链不可删除: {slug}")
    return DeleteResponse()


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
