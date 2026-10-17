from __future__ import annotations

import csv
import io
import urllib.parse

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.api.auth.dependencies import require_admin
from app.api.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.domain.identity import AuthenticatedUser
from app.modules.industry_classification.public import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportFileRequest,
    ImportPreviewResponse,
    IndustryHierarchyResponse,
    IndustryImportConflictError,
    IndustryImportError,
    IndustryImportTokenNotFoundError,
    IndustryListResponse,
    IndustryRecord,
    IndustryRecordConflictError,
    IndustryRecordInput,
    IndustryRefreshError,
    IndustryStatusResponse,
    IndustryUpdateRequest,
    MutationResponse,
    RefreshPolicyRequest,
    RefreshResponse,
    commit_import,
    create_manual,
    delete_record,
    get_record,
    get_record_by_id,
    get_refresh_state,
    hierarchy,
    list_records,
    preview_import,
    refresh_a_share_industries,
    stats,
    update_manual,
    update_refresh_state,
)
from app.modules.master_data_revision import MasterDataConflictError

router = APIRouter()


@router.get("/industries", response_model=IndustryHierarchyResponse)
def get_industries(
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$"),
    level1: str = "",
    level2: str = "",
):
    return hierarchy(market_group=market_group, level1=level1, level2=level2)


@router.get("/stocks", response_model=IndustryListResponse)
def get_stocks(
    query: str = Query(default="", max_length=128),
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$"),
    level1: str = "",
    level2: str = "",
    level3: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    items, total = list_records(
        query=query,
        market_group=market_group,
        level1=level1,
        level2=level2,
        level3=level3,
        page=page,
        page_size=page_size,
    )
    return IndustryListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/stocks/{stock_code}", response_model=IndustryRecord)
def get_stock(stock_code: str):
    record = get_record(stock_code)
    if record is None:
        raise NotFoundError("未找到该股票的申万行业数据", code="industry.record_not_found")
    return record


@router.get("/status", response_model=IndustryStatusResponse)
def get_status():
    return IndustryStatusResponse(stats=stats(), refresh=get_refresh_state())


@router.post(
    "/records",
    response_model=MutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_record(
    request: IndustryRecordInput,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    try:
        return MutationResponse(id=create_manual(request))
    except IndustryRecordConflictError as exc:
        raise ConflictError(str(exc), code="industry.stock_code_exists") from exc


@router.put("/records/{record_id}", response_model=MutationResponse)
def update_record(
    record_id: int,
    request: IndustryUpdateRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    if get_record_by_id(record_id) is None:
        raise NotFoundError("行业记录不存在", code="industry.record_not_found")
    try:
        update_manual(record_id, request, expected_revision=request.expected_revision)
    except MasterDataConflictError as exc:
        raise ConflictError(str(exc), code="master_data.edit_conflict") from exc
    except IndustryRecordConflictError as exc:
        raise ConflictError(str(exc), code="industry.stock_code_exists") from exc
    return MutationResponse(id=record_id)


@router.delete("/records/{record_id}", response_model=MutationResponse)
def remove_record(
    record_id: int,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    if not delete_record(record_id):
        raise NotFoundError("行业记录不存在", code="industry.record_not_found")
    return MutationResponse(id=record_id)


@router.post("/import/preview", response_model=ImportPreviewResponse)
def preview_excel_import(
    request: ImportFileRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    try:
        return preview_import(request)
    except IndustryImportError as exc:
        raise BadRequestError(str(exc), code="industry.invalid_import_file") from exc


@router.post("/import/commit", response_model=ImportCommitResponse)
def commit_excel_import(
    request: ImportCommitRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    try:
        return ImportCommitResponse(**commit_import(request))
    except IndustryImportError as exc:
        raise BadRequestError(str(exc), code="industry.invalid_import_file") from exc
    except IndustryImportTokenNotFoundError as exc:
        raise NotFoundError(str(exc), code="industry.import_token_not_found") from exc
    except IndustryImportConflictError as exc:
        raise ConflictError(str(exc), code="industry.import_conflict") from exc


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_industries(
    _admin: AuthenticatedUser = Depends(require_admin),
):
    try:
        return await refresh_a_share_industries()
    except IndustryRefreshError as exc:
        raise ServiceUnavailableError(str(exc), code="industry.refresh_failed") from exc


@router.put("/refresh-policy", response_model=IndustryStatusResponse)
def update_refresh_policy(
    request: RefreshPolicyRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    update_refresh_state(
        enabled=request.enabled,
        interval_seconds=request.interval_seconds,
    )
    return IndustryStatusResponse(stats=stats(), refresh=get_refresh_state())


@router.get("/export")
def export_industries(
    query: str = Query(default="", max_length=128),
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$"),
    level1: str = "",
    level2: str = "",
    level3: str = "",
):
    items, _ = list_records(
        query=query,
        market_group=market_group,
        level1=level1,
        level2=level2,
        level3=level3,
        page=1,
        page_size=0,
    )

    output = io.StringIO()
    # Write UTF-8 BOM for Excel compatibility
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "股票代码",
        "公司简称",
        "市场",
        "一级行业",
        "二级行业",
        "三级行业",
        "行业代码",
        "数据来源",
        "更新时间",
    ])
    for item in items:
        writer.writerow([
            item.get("stock_code", ""),
            item.get("stock_name", ""),
            item.get("market_group", ""),
            item.get("sw_level1_name", ""),
            item.get("sw_level2_name", ""),
            item.get("sw_level3_name", ""),
            item.get("sw_industry_code", ""),
            item.get("source", ""),
            item.get("updated_at", ""),
        ])

    csv_data = output.getvalue().encode("utf-8")
    filename = "industry_classification_export.csv"
    encoded_fn = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_fn}",
        "Content-Type": "text/csv; charset=utf-8",
    }
    return StreamingResponse(io.BytesIO(csv_data), headers=headers, media_type="text/csv")

