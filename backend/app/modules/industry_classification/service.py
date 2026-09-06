from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.financial_data.stock.public import update_industry_mapping_sw_files
from app.modules.industry_classification import importer, repository
from app.modules.industry_classification.models import (
    ImportCommitRequest,
    ImportFileRequest,
    ImportPreviewResponse,
    RefreshResponse,
)


class IndustryImportTokenNotFoundError(LookupError):
    pass


class IndustryImportConflictError(RuntimeError):
    pass


class IndustryRefreshError(RuntimeError):
    pass


def _effective_date(value: object) -> str | None:
    return str(value) if value is not None else None


def _source_version(request: ImportFileRequest) -> str:
    return request.source_version or importer.default_source_version(request.filename)


def preview_import(request: ImportFileRequest) -> ImportPreviewResponse:
    content = importer.decode_file(request.content_base64)
    parsed = importer.parse_data(content, request.filename)
    source_version = _source_version(request)
    counts = repository.classify_import_records(parsed.records)
    token = secrets.token_urlsafe(32)
    summary = {
        "total_rows": parsed.total_rows,
        "valid_rows": len(parsed.records),
        "added_rows": counts["added"],
        "updated_rows": counts["updated"],
        "unchanged_rows": counts["unchanged"],
        "skipped_rows": counts["skipped"],
        "conflict_rows": parsed.conflict_rows,
        "invalid_rows": parsed.invalid_rows,
    }
    repository.save_import_batch(
        token=token,
        content_hash=parsed.content_hash,
        filename=request.filename,
        source_version=source_version,
        effective_date=_effective_date(request.effective_date),
        status="previewed",
        summary=summary,
        warnings=parsed.warnings,
    )
    return ImportPreviewResponse(
        import_token=token,
        content_hash=parsed.content_hash,
        **summary,
        warnings=parsed.warnings,
        sample=parsed.records[:20],
    )


def commit_import(request: ImportCommitRequest) -> dict[str, int]:
    batch = repository.get_import_batch(request.import_token)
    if batch is None:
        raise IndustryImportTokenNotFoundError("导入令牌不存在，请重新预检")
    if batch["status"] != "previewed":
        raise IndustryImportConflictError("该导入批次已提交或已失效，请重新预检")

    content = importer.decode_file(request.content_base64)
    parsed = importer.parse_data(content, request.filename)
    source_version = _source_version(request)
    effective_date = _effective_date(request.effective_date)
    expected = (
        str(batch["content_hash"]),
        str(batch["filename"]),
        str(batch["source_version"]),
        str(batch["effective_date"] or ""),
    )
    actual = (
        parsed.content_hash,
        request.filename,
        source_version,
        effective_date or "",
    )
    if actual != expected:
        raise IndustryImportConflictError("文件或导入参数与预检时不一致，请重新预检")

    try:
        return repository.commit_import_batch(
            token=request.import_token,
            records=parsed.records,
            source_version=source_version,
            effective_date=effective_date,
            force_override=request.force_override,
            content_hash=parsed.content_hash,
            filename=request.filename,
            total_rows=parsed.total_rows,
            conflict_rows=parsed.conflict_rows,
            invalid_rows=parsed.invalid_rows,
            warnings=parsed.warnings,
        )
    except repository.ImportBatchStateChangedError as exc:
        raise IndustryImportConflictError(str(exc)) from exc


async def refresh_a_share_industries() -> RefreshResponse:
    repository.update_refresh_state(last_started_at=datetime.now().isoformat(timespec="seconds"))
    try:
        result = await call_blocking(
            update_industry_mapping_sw_files,
            semaphore=database_semaphore,
        )
        mappings = {
            level: mapping
            for level, (mapping, _industry_list) in result.items()
            if level in {1, 2, 3} and mapping
        }
        if not mappings:
            raise IndustryRefreshError("申万行业上游未返回有效数据，已保留现有数据")
        counts = await call_blocking(
            repository.upsert_a_share_mappings,
            mappings,
            semaphore=database_semaphore,
        )
    except Exception as exc:
        repository.update_refresh_state(
            last_failed_at=datetime.now().isoformat(timespec="seconds"),
            last_error=str(exc)[:1000],
        )
        if isinstance(exc, IndustryRefreshError):
            raise
        raise IndustryRefreshError(f"申万行业自动更新失败: {exc}") from exc

    repository.update_refresh_state(
        last_succeeded_at=datetime.now().isoformat(timespec="seconds"),
        last_error=None,
        last_added=counts["added"],
        last_updated=counts["updated"],
        last_unchanged=counts["unchanged"],
    )
    return RefreshResponse(**counts, provider="sina_akshare")


def refresh_is_due(state: dict[str, Any], *, now: datetime | None = None) -> bool:
    if not state["enabled"]:
        return False
    last_succeeded = state.get("last_succeeded_at")
    if not last_succeeded:
        return True
    try:
        succeeded_at = datetime.fromisoformat(str(last_succeeded))
    except ValueError:
        return True
    current = now or datetime.now()
    return (current - succeeded_at).total_seconds() >= int(state["interval_seconds"])


async def scheduled_refresh() -> RefreshResponse | None:
    state = repository.get_refresh_state()
    if not refresh_is_due(state):
        return None
    return await refresh_a_share_industries()
