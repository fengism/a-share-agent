from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.modules.code_normalization import normalize_imported_stock_code
from app.modules.import_limits import MAX_IMPORT_BASE64_CHARS, MAX_IMPORT_FILE_BYTES
from app.modules.stock_concept.models import StockConceptRecordInput

_MAX_FILE_SIZE = MAX_IMPORT_FILE_BYTES


class ConceptImportError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedConceptFile:
    content_hash: str
    total_rows: int
    records: list[dict[str, Any]]
    invalid_rows: int
    warnings: list[str]


def decode_file(content_base64: str) -> bytes:
    if len(content_base64) > MAX_IMPORT_BASE64_CHARS:
        raise ConceptImportError("上传文件不能超过 50 MiB")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ConceptImportError("上传文件不是有效的 Base64 内容") from exc
    if not content:
        raise ConceptImportError("上传文件为空")
    if len(content) > _MAX_FILE_SIZE:
        raise ConceptImportError("上传文件不能超过 50 MB")
    return content


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_stock_code(raw_val: object) -> tuple[str, str, str]:
    return normalize_imported_stock_code(_text(raw_val))


def _extract_concepts(val: object) -> list[str]:
    raw = _text(val)
    if not raw:
        return []
    parts = raw.replace("；", ";").replace(",", ";").replace("，", ";").split(";")
    res: list[str] = []
    seen: set[str] = set()
    for part in parts:
        s = part.strip()
        if s and s not in seen:
            seen.add(s)
            res.append(s)
    return res


def parse_data(content: bytes, filename: str) -> ParsedConceptFile:
    content_hash = hashlib.sha256(content).hexdigest()
    lower_fn = filename.lower()
    try:
        if lower_fn.endswith(".csv"):
            # try utf-8, then gbk
            try:
                frame = pd.read_csv(BytesIO(content), dtype=str, encoding="utf-8-sig")
            except Exception:
                frame = pd.read_csv(BytesIO(content), dtype=str, encoding="gbk")
        else:
            frame = pd.read_excel(BytesIO(content), dtype=str)
    except Exception as exc:
        raise ConceptImportError(f"无法读取文件，请确认是有效的 CSV 或 Excel 格式: {exc}") from exc

    frame.columns = [str(col).strip() for col in frame.columns]

    # 匹配列名
    code_col = None
    for candidate in ("股票代码", "代码", "stock_code", "code"):
        if candidate in frame.columns:
            code_col = candidate
            break

    name_col = None
    for candidate in ("公司简称", "股票简称", "简称", "股票名称", "名称", "stock_name", "name"):
        if candidate in frame.columns:
            name_col = candidate
            break

    exchange_col = next((col for col in ("交易所", "市场", "exchange") if col in frame.columns), None)

    concept_col = None
    for candidate in ("所属概念", "概念", "概念板块", "concepts", "concept"):
        if candidate in frame.columns:
            concept_col = candidate
            break

    if not code_col:
        raise ConceptImportError("文件中缺少【股票代码】列")
    if not concept_col:
        raise ConceptImportError("文件中缺少【所属概念】列")

    records: list[dict[str, Any]] = []
    invalid_rows = 0
    warnings: list[str] = []
    seen_codes: set[str] = set()
    duplicate_codes: set[str] = set()

    for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
        stock_code, suffix, market = normalize_imported_stock_code(
            _text(row[code_col]), _text(row[exchange_col]) if exchange_col else ""
        )
        if not stock_code:
            invalid_rows += 1
            warnings.append(f"第 {row_number} 行股票代码无效，已跳过")
            continue
        if stock_code in seen_codes:
            invalid_rows += 1
            duplicate_codes.add(stock_code)
            continue

        stock_name = _text(row[name_col]) if name_col else ""
        concepts = _extract_concepts(row[concept_col])

        values = {
            "market_group": market,
            "exchange_suffix": suffix,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "concepts": concepts,
        }

        try:
            validated = StockConceptRecordInput.model_validate(values)
        except ValidationError as exc:
            invalid_rows += 1
            fields = "、".join(sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]}))
            warnings.append(f"第 {row_number} 行字段校验失败（{fields or '股票身份'}），已跳过")
            continue
        seen_codes.add(stock_code)
        records.append(validated.model_dump(include=set(values)))

    if duplicate_codes:
        sample = "、".join(sorted(duplicate_codes)[:5])
        warnings.append(f"发现重复股票代码并跳过后续记录: {sample}")

    return ParsedConceptFile(
        content_hash=content_hash,
        total_rows=len(frame),
        records=records,
        invalid_rows=invalid_rows,
        warnings=warnings,
    )


def default_source_version(filename: str) -> str:
    return Path(filename).stem[:128]
