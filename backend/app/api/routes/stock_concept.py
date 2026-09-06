from __future__ import annotations

import csv
import io
import sqlite3
import urllib.parse

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.api.auth.dependencies import require_admin
from app.api.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.domain.identity import AuthenticatedUser
from app.modules.stock_concept.importer import ConceptImportError
from app.modules.stock_concept.public import (
    ConceptImportCommitRequest,
    ConceptImportCommitResponse,
    ConceptImportConflictError,
    ConceptImportFileRequest,
    ConceptImportPreviewResponse,
    ConceptImportTokenNotFoundError,
    ConceptListResponse,
    ConceptMutationResponse,
    ConceptStatusResponse,
    StockConceptListResponse,
    StockConceptRecord,
    StockConceptRecordInput,
    commit_import,
    create_manual,
    delete_record,
    get_all_concepts,
    get_record,
    get_record_by_id,
    list_records,
    preview_import,
    stats,
    update_manual,
)

router = APIRouter()


@router.get("/concepts", response_model=ConceptListResponse)
def get_concepts(
    query: str = Query(default="", max_length=128),
    limit: int = Query(default=500, ge=1, le=2000),
):
    items = get_all_concepts(query=query, limit=limit)
    return ConceptListResponse(items=items, total=len(items))


@router.get("/stocks", response_model=StockConceptListResponse)
def get_stocks(
    query: str = Query(default="", max_length=128),
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$"),
    concept: str = Query(default="", max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    items, total = list_records(
        query=query,
        market_group=market_group,
        concept=concept,
        page=page,
        page_size=page_size,
    )
    return StockConceptListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/stocks/{stock_code}", response_model=StockConceptRecord)
def get_stock(stock_code: str):
    record = get_record(stock_code)
    if record is None:
        raise NotFoundError("未找到该股票的概念数据", code="stock_concept.record_not_found")
    return record


@router.get("/status", response_model=ConceptStatusResponse)
def get_status():
    return ConceptStatusResponse(stats=stats())


@router.post(
    "/records",
    response_model=ConceptMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_record(
    request: StockConceptRecordInput,
    _: AuthenticatedUser = Depends(require_admin),
):
    try:
        record_id = create_manual(request)
    except sqlite3.IntegrityError as exc:
        raise ConflictError(
            f"股票代码 {request.stock_code} 已存在",
            code="stock_concept.record_exists",
        ) from exc
    return ConceptMutationResponse(success=True, id=record_id)


@router.put(
    "/records/{record_id}",
    response_model=ConceptMutationResponse,
)
def update_record(
    record_id: int,
    request: StockConceptRecordInput,
    _: AuthenticatedUser = Depends(require_admin),
):
    current = get_record_by_id(record_id)
    if current is None:
        raise NotFoundError("要修改的概念记录不存在", code="stock_concept.record_not_found")
    try:
        success = update_manual(record_id, request)
    except sqlite3.IntegrityError as exc:
        raise ConflictError(
            f"股票代码 {request.stock_code} 已存在",
            code="stock_concept.record_exists",
        ) from exc
    return ConceptMutationResponse(success=success, id=record_id)


@router.delete(
    "/records/{record_id}",
    response_model=ConceptMutationResponse,
)
def remove_record(
    record_id: int,
    _: AuthenticatedUser = Depends(require_admin),
):
    current = get_record_by_id(record_id)
    if current is None:
        raise NotFoundError("要删除的概念记录不存在", code="stock_concept.record_not_found")
    return ConceptMutationResponse(success=delete_record(record_id), id=record_id)


@router.post(
    "/import/preview",
    response_model=ConceptImportPreviewResponse,
)
def preview_import_file(
    request: ConceptImportFileRequest,
    _: AuthenticatedUser = Depends(require_admin),
):
    try:
        return preview_import(request)
    except ConceptImportError as exc:
        raise BadRequestError(str(exc), code="stock_concept.invalid_import_file") from exc


@router.post(
    "/import/commit",
    response_model=ConceptImportCommitResponse,
)
def commit_import_file(
    request: ConceptImportCommitRequest,
    _: AuthenticatedUser = Depends(require_admin),
):
    try:
        summary = commit_import(request)
        return ConceptImportCommitResponse(**summary)
    except ConceptImportTokenNotFoundError as exc:
        raise NotFoundError(str(exc), code="stock_concept.import_token_not_found") from exc
    except ConceptImportConflictError as exc:
        raise ConflictError(str(exc), code="stock_concept.import_conflict") from exc
    except ConceptImportError as exc:
        raise BadRequestError(str(exc), code="stock_concept.invalid_import_file") from exc


@router.get("/export")
def export_concepts(
    query: str = Query(default="", max_length=128),
    market_group: str = Query(default="", pattern="^(|A|HK|OVERSEAS)$"),
    concept: str = Query(default="", max_length=128),
):
    items, _ = list_records(
        query=query,
        market_group=market_group,
        concept=concept,
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
        "所属概念",
        "数据来源",
        "更新时间",
    ])
    for item in items:
        concepts_list = item.get("concepts") or []
        writer.writerow([
            item.get("stock_code", ""),
            item.get("stock_name", ""),
            item.get("market_group", ""),
            "；".join(concepts_list),
            item.get("source", ""),
            item.get("updated_at", ""),
        ])

    csv_data = output.getvalue().encode("utf-8")
    filename = "stock_concept_export.csv"
    encoded_fn = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_fn}",
        "Content-Type": "text/csv; charset=utf-8",
    }
    return StreamingResponse(io.BytesIO(csv_data), headers=headers, media_type="text/csv")

