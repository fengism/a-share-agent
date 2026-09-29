from __future__ import annotations

import secrets

from app.modules.stock_concept import importer, repository
from app.modules.stock_concept.models import (
    ConceptImportCommitRequest,
    ConceptImportFileRequest,
    ConceptImportPreviewResponse,
)


class ConceptImportTokenNotFoundError(LookupError):
    pass


class ConceptImportConflictError(RuntimeError):
    pass


def _source_version(request: ConceptImportFileRequest) -> str:
    return request.source_version or importer.default_source_version(request.filename)


def preview_import(request: ConceptImportFileRequest) -> ConceptImportPreviewResponse:
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
        "invalid_rows": parsed.invalid_rows,
    }
    repository.save_import_batch(
        token=token,
        content_hash=parsed.content_hash,
        filename=request.filename,
        source_version=source_version,
        status="previewed",
        summary=summary,
        warnings=parsed.warnings,
    )
    return ConceptImportPreviewResponse(
        import_token=token,
        content_hash=parsed.content_hash,
        **summary,
        warnings=parsed.warnings,
        sample=parsed.records[:20],
    )


def commit_import(request: ConceptImportCommitRequest) -> dict[str, int]:
    batch = repository.get_import_batch(request.import_token)
    if batch is None:
        raise ConceptImportTokenNotFoundError("导入令牌不存在，请重新预检")
    if batch["status"] != "previewed":
        raise ConceptImportConflictError("该导入批次已提交或已失效，请重新预检")

    content = importer.decode_file(request.content_base64)
    parsed = importer.parse_data(content, request.filename)
    source_version = _source_version(request)
    expected = (
        str(batch["content_hash"]),
        str(batch["filename"]),
        str(batch["source_version"]),
    )
    actual = (
        parsed.content_hash,
        request.filename,
        source_version,
    )
    if actual != expected:
        raise ConceptImportConflictError("文件或导入参数与预检时不一致，请重新预检")

    try:
        return repository.commit_import_batch(
            token=request.import_token,
            records=parsed.records,
            source_version=source_version,
            force_override=request.force_override,
        )
    except repository.ImportBatchStateChangedError as exc:
        raise ConceptImportConflictError(str(exc)) from exc
