from __future__ import annotations

import logging
import secrets
from typing import Any

from app.modules.stock_concept import importer, repository
from app.modules.stock_concept.models import (
    ConceptImportCommitRequest,
    ConceptImportFileRequest,
    ConceptImportPreviewResponse,
)

logger = logging.getLogger(__name__)


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


async def auto_enrich_pending_concepts(
    batch_size: int = 50,
    delay_seconds: float = 0.5,
) -> dict[str, int]:
    """后台平滑队列：自动为缺少概念或概念为空的 A 股从同花顺抓取官方概念。

    Param:
        batch_size: 单批处理最大数量，默认 50
        delay_seconds: 每只股票抓取间隔（秒），避免频控，默认 0.5s
    Return:
        {'processed': 处理数, 'enriched': 成功补全数, 'remaining': 剩余缺失数}
    """
    import asyncio

    from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore
    from app.infrastructure.providers.ths.provider import ths_provider

    def _query_pending() -> tuple[list[tuple[str, str]], int]:
        conn = repository._connection()
        # 寻找 A 股中尚未维护概念或概念为空列表的股票
        rows = conn.execute(
            """
            SELECT p.stock_code, p.stock_name
            FROM stock_basic_profiles p
            LEFT JOIN stock_concept_mappings c ON p.stock_code = c.stock_code
            WHERE p.market_group = 'A'
              AND (c.stock_code IS NULL OR c.concepts_json = '[]' OR c.concepts_json IS NULL)
            ORDER BY p.id ASC
            """
        ).fetchall()
        total_missing = len(rows)
        return [(str(r[0]), str(r[1])) for r in rows[:batch_size]], total_missing

    pending_list, total_missing = await call_blocking(_query_pending, semaphore=database_semaphore)
    if not pending_list:
        return {"processed": 0, "enriched": 0, "remaining": 0}

    enriched_count = 0
    records_to_upsert: list[dict[str, Any]] = []

    for stock_code, stock_name in pending_list:
        try:
            concepts = await call_blocking(
                ths_provider.fetch_stock_concepts,
                stock_code,
                semaphore=misc_semaphore,
            )
            if concepts:
                suffix = stock_code.split(".")[-1] if "." in stock_code else "SZ"
                records_to_upsert.append({
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "market_group": "A",
                    "exchange_suffix": suffix,
                    "concepts": concepts,
                })
                enriched_count += 1
        except Exception as exc:
            logger.debug("auto_enrich_pending_concepts 抓取股票 %s 概念失败: %s", stock_code, exc)

        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    if records_to_upsert:
        await call_blocking(
            repository.upsert_import_records,
            records_to_upsert,
            source_version="ths_online_auto",
            force_override=False,
            semaphore=database_semaphore,
        )

    return {
        "processed": len(pending_list),
        "enriched": enriched_count,
        "remaining": max(0, total_missing - len(pending_list)),
    }

