"""个股基础资料库 API 路由。

提供个股基础资料（名称、代码、上市市场、上市时间、主营业务、经营范围等）
的查询、统计、批量导入/导出、编辑、补充更新与交易所名录同步。
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.auth.dependencies import require_admin
from app.api.errors import BadRequestError, ConflictError, NotFoundError
from app.domain.identity import AuthenticatedUser
from app.modules.master_data_revision import MasterDataConflictError
from app.modules.stock_profile.importer import ProfileImportError
from app.modules.stock_profile.models import (
    StockBasicProfileInput,
    StockBasicProfileListResponse,
    StockBasicProfileRecord,
    StockBasicProfileSummary,
    StockProfileEnrichResponse,
    StockProfileImportFileRequest,
    StockProfileImportResponse,
    StockProfileSyncResponse,
    StockProfileUpdateRequest,
)
from app.modules.stock_profile.public import (
    enrich_stock_profile,
    export_profiles_csv,
    get_profile,
    get_profile_summary,
    get_stock_profile_record_by_id,
    import_profiles,
    list_profiles,
    remove_profile,
    save_profile,
    sync_exchange_master_data,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary", response_model=StockBasicProfileSummary)
def get_summary() -> StockBasicProfileSummary:
    """获取个股基础资料库统计概览（股票总数、主营覆盖率、板块分布等）。"""
    return get_profile_summary()


@router.get("/records", response_model=StockBasicProfileListResponse)
def get_records(
    q: str = Query(default="", description="股票代码或名称模糊搜索"),
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$", description="市场组别"),
    exchange: str = Query(default="", description="交易所(SH/SZ/BJ/HK)"),
    board: str = Query(default="", description="上市板块(主板/科创板/创业板/北交所/港股主板)"),
    has_business: bool | None = Query(default=None, description="是否已录入主营业务"),
    has_listing_date: bool | None = Query(default=None, description="是否有上市时间"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=500, description="每页条数"),
    sort_by: str = Query(default="stock_code", description="排序字段"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc|ASC|DESC)$", description="排序方向"),
) -> StockBasicProfileListResponse:
    """分页筛选个股基础资料列表。"""
    return list_profiles(
        query=q,
        market_group=market_group,
        exchange=exchange,
        board=board,
        has_business=has_business,
        has_listing_date=has_listing_date,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/records/export")
def export_records(
    q: str = Query(default="", max_length=128, description="股票代码或名称模糊搜索"),
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$", description="市场组别"),
    exchange: str = Query(default="", description="交易所(SH/SZ/BJ/HK)"),
    board: str = Query(default="", description="上市板块"),
    has_business: bool | None = Query(default=None, description="是否已录入主营业务"),
    has_listing_date: bool | None = Query(default=None, description="是否有上市时间"),
) -> StreamingResponse:
    """按筛选条件导出全部个股基础资料为 CSV（带 BOM，Excel 可直接打开）。"""
    csv_bytes, disposition = export_profiles_csv(
        query=q,
        market_group=market_group,
        exchange=exchange,
        board=board,
        has_business=has_business,
        has_listing_date=has_listing_date,
    )
    return StreamingResponse(io.BytesIO(csv_bytes), headers={"Content-Disposition": disposition}, media_type="text/csv")


@router.post("/records/import", response_model=StockProfileImportResponse)
def import_records(
    request: StockProfileImportFileRequest,
    _: AuthenticatedUser = Depends(require_admin),
) -> StockProfileImportResponse:
    """批量导入个股基础资料（Base64 编码的 Excel/CSV），内容无变化的行自动跳过。"""
    try:
        return import_profiles(request)
    except ProfileImportError as exc:
        raise BadRequestError(str(exc), code="stock_profile.invalid_import_file") from exc


@router.get("/records/{code}", response_model=StockBasicProfileRecord)
def get_record_by_code(code: str) -> StockBasicProfileRecord:
    """按股票代码获取个股基础资料（支持 600519 或 600519.SH）。"""
    record = get_profile(code)
    if not record:
        raise HTTPException(status_code=404, detail=f"未找到股票资料记录: {code}")
    return record


@router.post("/records", response_model=StockBasicProfileRecord)
def create_or_update_record(
    payload: StockBasicProfileInput,
    _: AuthenticatedUser = Depends(require_admin),
) -> StockBasicProfileRecord:
    """手动创建个股基础资料；已存在时返回冲突，请使用带修订标识的编辑接口。"""
    try:
        return save_profile(payload, source="manual", is_manual_override=True, create_only=True)
    except MasterDataConflictError as exc:
        raise ConflictError(str(exc), code="master_data.record_exists") from exc


@router.put("/records/{record_id}", response_model=StockBasicProfileRecord)
def update_record_by_id(
    record_id: int,
    payload: StockProfileUpdateRequest,
    _: AuthenticatedUser = Depends(require_admin),
) -> StockBasicProfileRecord:
    """按记录 ID 手工保存个股基础资料（股票代码不可变更）。"""
    existing = get_stock_profile_record_by_id(record_id)
    if existing is None:
        raise NotFoundError(f"未找到记录 ID: {record_id}", code="stock_profile.record_not_found")
    if existing["stock_code"] != payload.stock_code:
        raise BadRequestError(
            f"记录 {record_id} 的股票代码为 {existing['stock_code']}，不允许通过该接口修改；"
            "如需变更请删除后重建",
            code="stock_profile.code_immutable",
        )
    try:
        return save_profile(payload, source="manual", is_manual_override=True, expected_revision=payload.expected_revision)
    except MasterDataConflictError as exc:
        raise ConflictError(str(exc), code="master_data.edit_conflict") from exc


@router.delete("/records/{record_id}")
def delete_record_by_id(
    record_id: int,
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, bool]:
    """删除指定的个股基础资料记录。"""
    success = remove_profile(record_id)
    if not success:
        raise NotFoundError(f"未找到记录 ID: {record_id}", code="stock_profile.record_not_found")
    return {"success": True}


@router.post("/enrich/{code}", response_model=StockProfileEnrichResponse)
def enrich_record(
    code: str,
    force: bool = Query(default=False, description="是否强制刷新"),
    _: AuthenticatedUser = Depends(require_admin),
) -> StockProfileEnrichResponse:
    """补充个股资料：库中已有主营信息时直接返回，缺失才从同花顺/东方财富抓取并持久化（force=true 强制刷新）。"""
    return enrich_stock_profile(code, force=force)


@router.post("/sync-master", response_model=StockProfileSyncResponse)
async def sync_master(_: AuthenticatedUser = Depends(require_admin)) -> StockProfileSyncResponse:
    """从官方交易所名录与申万行业数据全量同步/更新个股基础资料库。"""
    return await sync_exchange_master_data()
