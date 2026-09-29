"""个股资料批量导入：Excel/CSV 解析、代码归一与行级容错。"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.modules.code_normalization import normalize_imported_stock_code
from app.modules.import_limits import MAX_IMPORT_BASE64_CHARS, MAX_IMPORT_FILE_BYTES
from app.modules.stock_profile.models import StockBasicProfileInput

_MAX_FILE_SIZE = MAX_IMPORT_FILE_BYTES

_CODE_CANDIDATES = ("股票代码", "代码", "stock_code", "code")
_EXCHANGE_HINT_CANDIDATES = ("交易所", "市场", "exchange")
_COLUMN_CANDIDATES: dict[str, tuple[str, ...]] = {
    "board": ("板块", "board"),
    "stock_name": ("股票简称", "简称", "名称", "stock_name", "name"),
    "listing_date": ("上市日期", "listing_date"),
    "main_business": ("主营业务", "main_business"),
    "business_scope": ("经营范围", "business_scope"),
    "products": ("主要产品", "产品", "products"),
    "industry": ("所属行业", "行业", "industry"),
    "sw_level1_name": ("申万一级行业", "一级行业", "sw_level1_name"),
    "sw_level2_name": ("申万二级行业", "二级行业", "sw_level2_name"),
    "sw_level3_name": ("申万三级行业", "三级行业", "sw_level3_name"),
    "province": ("省份", "province"),
    "city": ("城市", "city"),
    "legal_repr": ("法定代表人", "legal_repr"),
    "registered_capital": ("注册资本", "registered_capital"),
    "setup_date": ("成立日期", "setup_date"),
    "website": ("网址", "网站", "website"),
    "company_intro": ("公司简介", "company_intro"),
}


class ProfileImportError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedProfileFile:
    content_hash: str
    total_rows: int
    records: list[dict[str, Any]]
    invalid_rows: int
    warnings: list[str] = field(default_factory=list)


def decode_file(content_base64: str) -> bytes:
    if len(content_base64) > MAX_IMPORT_BASE64_CHARS:
        raise ProfileImportError("上传文件不能超过 50 MiB")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ProfileImportError("上传文件不是有效的 Base64 内容") from exc
    if not content:
        raise ProfileImportError("上传文件为空")
    if len(content) > _MAX_FILE_SIZE:
        raise ProfileImportError("上传文件不能超过 50 MB")
    return content


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_date(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    candidate = text.replace("/", "-")[:10]
    try:
        return datetime.fromisoformat(candidate).date().isoformat()
    except ValueError:
        return text[:32]  # 无法解析的日期保留原文，便于用户核对


def _match_column(frame_columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in frame_columns:
            return candidate
    return None


def parse_data(content: bytes, filename: str) -> ParsedProfileFile:
    content_hash = hashlib.sha256(content).hexdigest()
    lower_fn = filename.lower()
    try:
        if lower_fn.endswith(".csv"):
            try:
                frame = pd.read_csv(BytesIO(content), dtype=str, encoding="utf-8-sig")
            except Exception:
                frame = pd.read_csv(BytesIO(content), dtype=str, encoding="gbk")
        else:
            frame = pd.read_excel(BytesIO(content), dtype=str)
    except Exception as exc:
        raise ProfileImportError(f"无法读取文件，请确认是有效的 CSV 或 Excel 格式: {exc}") from exc

    frame.columns = [str(col).strip() for col in frame.columns]
    columns = list(frame.columns)

    code_col = _match_column(columns, _CODE_CANDIDATES)
    if not code_col:
        raise ProfileImportError("文件中缺少【股票代码】列")

    exchange_col = _match_column(columns, _EXCHANGE_HINT_CANDIDATES)
    field_cols = {
        key: _match_column(columns, candidates)
        for key, candidates in _COLUMN_CANDIDATES.items()
    }

    records: list[dict[str, Any]] = []
    invalid_rows = 0
    warnings: list[str] = []
    if any(field_cols[field] for field in ("sw_level1_name", "sw_level2_name", "sw_level3_name")):
        warnings.append("申万行业列仅供导出参考，导入不更新分类；请在行业基础数据页维护")
    seen_codes: set[str] = set()
    duplicate_codes: set[str] = set()

    for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
        exchange_hint = _text(row[exchange_col]) if exchange_col else ""
        normalized_code, _suffix, market_group = normalize_imported_stock_code(
            _text(row[code_col]), exchange_hint
        )
        if not normalized_code:
            invalid_rows += 1
            warnings.append(f"第 {row_number} 行股票代码无效，已跳过")
            continue
        if normalized_code in seen_codes:
            invalid_rows += 1
            duplicate_codes.add(normalized_code)
            continue

        values: dict[str, Any] = {
            "stock_code": normalized_code,
            "market_group": market_group,
            "exchange": _suffix,
            "stock_name": _text(row[field_cols["stock_name"]]) if field_cols["stock_name"] else "",
            "board": _text(row[field_cols["board"]]) if field_cols["board"] else "",
            "listing_date": _normalize_date(row[field_cols["listing_date"]]) if field_cols["listing_date"] else None,
            "setup_date": _normalize_date(row[field_cols["setup_date"]]) if field_cols["setup_date"] else None,
            "source_version": Path(filename).stem[:128],
        }
        for key in (
            "main_business",
            "business_scope",
            "products",
            "industry",
            "sw_level1_name",
            "sw_level2_name",
            "sw_level3_name",
            "province",
            "city",
            "legal_repr",
            "registered_capital",
            "website",
            "company_intro",
        ):
            col = field_cols[key]
            values[key] = _text(row[col]) if col else ""
        # 经输入模型归一：板块/交易所缺省时按代码推断，字段长度得到校验
        try:
            record = StockBasicProfileInput.model_validate(values).model_dump()
        except ValidationError as exc:
            invalid_rows += 1
            fields = "、".join(sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]}))
            warnings.append(f"第 {row_number} 行字段校验失败（{fields or '股票身份'}），已跳过")
            continue
        seen_codes.add(normalized_code)
        records.append(record)

    if duplicate_codes:
        sample = "、".join(sorted(duplicate_codes)[:5])
        warnings.append(f"发现重复股票代码并跳过后续记录: {sample}")

    return ParsedProfileFile(
        content_hash=content_hash,
        total_rows=len(frame),
        records=records,
        invalid_rows=invalid_rows,
        warnings=warnings,
    )


def default_source_version(filename: str) -> str:
    return Path(filename).stem[:128]
