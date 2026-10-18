from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.core.dataframes import clean_cell_text
from app.modules.code_normalization import normalize_imported_stock_code
from app.modules.import_limits import MAX_IMPORT_BASE64_CHARS, MAX_IMPORT_FILE_BYTES
from app.modules.industry_classification.models import IndustryRecordInput

_REQUIRED_SW_COLUMNS = (
    "交易所",
    "行业代码",
    "股票代码",
    "公司简称",
    "新版一级行业",
    "新版二级行业",
    "新版三级行业",
)
_MAX_FILE_SIZE = MAX_IMPORT_FILE_BYTES


class IndustryImportError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedIndustryFile:
    content_hash: str
    total_rows: int
    records: list[dict[str, Any]]
    invalid_rows: int
    conflict_rows: int
    warnings: list[str]


def decode_file(content_base64: str) -> bytes:
    if len(content_base64) > MAX_IMPORT_BASE64_CHARS:
        raise IndustryImportError("上传文件不能超过 50 MiB")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise IndustryImportError("上传文件不是有效的 Base64 内容") from exc
    if not content:
        raise IndustryImportError("上传文件为空")
    if len(content) > _MAX_FILE_SIZE:
        raise IndustryImportError("上传文件不能超过 50 MB")
    return content


def _normalize_code(value: object, exchange: str = "") -> tuple[str, str, str]:
    return normalize_imported_stock_code(clean_cell_text(value), exchange)


def _read_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    lower_fn = filename.lower()
    if lower_fn.endswith(".csv"):
        try:
            return pd.read_csv(BytesIO(content), dtype=str, encoding="utf-8-sig")
        except Exception as error:
            logging.getLogger(__name__).debug("UTF-8 解析失败，回退 GBK: %s", error)
            return pd.read_csv(BytesIO(content), dtype=str, encoding="gbk")
    else:
        try:
            return pd.read_excel(BytesIO(content), dtype=str)
        except Exception as exc:
            raise IndustryImportError(f"无法读取文件，请确认是有效的 CSV 或 Excel 文件: {exc}") from exc


def parse_data(content: bytes, filename: str = "upload.xlsx") -> ParsedIndustryFile:
    content_hash = hashlib.sha256(content).hexdigest()
    frame = _read_dataframe(content, filename)
    frame.columns = [str(column).strip() for column in frame.columns]

    # 匹配通用代码列
    code_col = None
    for candidate in ("股票代码", "代码", "stock_code", "code"):
        if candidate in frame.columns:
            code_col = candidate
            break

    # 匹配通用简称列
    name_col = None
    for candidate in ("公司简称", "股票简称", "简称", "股票名称", "名称", "stock_name", "name"):
        if candidate in frame.columns:
            name_col = candidate
            break

    # 匹配通用交易所列
    exchange_col = None
    for candidate in ("交易所", "上市地点", "exchange"):
        if candidate in frame.columns:
            exchange_col = candidate
            break

    # 匹配通用行业代码
    industry_code_col = None
    for candidate in ("行业代码", "sw_industry_code", "industry_code"):
        if candidate in frame.columns:
            industry_code_col = candidate
            break

    # 检查一级行业列
    l1_col = None
    for candidate in ("新版一级行业", "一级行业", "sw_level1_name", "所属同花顺行业", "所属行业", "行业"):
        if candidate in frame.columns:
            l1_col = candidate
            break

    # 检查二级行业列
    l2_col = None
    for candidate in ("新版二级行业", "二级行业", "sw_level2_name"):
        if candidate in frame.columns:
            l2_col = candidate
            break

    # 检查三级行业列
    l3_col = None
    for candidate in ("新版三级行业", "三级行业", "sw_level3_name"):
        if candidate in frame.columns:
            l3_col = candidate
            break

    if not code_col:
        raise IndustryImportError("文件缺少必填列【股票代码】")
    if not l1_col:
        raise IndustryImportError("文件缺少必填列：行业分类（例如【新版一级行业】或【所属行业】）")

    records: list[dict[str, Any]] = []
    invalid_rows = 0
    warnings: list[str] = []
    seen_codes: set[str] = set()
    duplicate_codes: set[str] = set()

    for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
        exchange_val = clean_cell_text(row[exchange_col]) if exchange_col else ""
        stock_code, suffix, market = _normalize_code(row[code_col], exchange_val)
        if not stock_code or not suffix:
            invalid_rows += 1
            warnings.append(f"第 {row_number} 行股票代码无效，已跳过")
            continue
        if stock_code in seen_codes:
            invalid_rows += 1
            duplicate_codes.add(stock_code)
            continue

        stock_name = clean_cell_text(row[name_col]) if name_col else ""
        industry_code = clean_cell_text(row[industry_code_col]) if industry_code_col else ""

        level1 = clean_cell_text(row[l1_col])
        level2 = clean_cell_text(row[l2_col]) if l2_col else ""
        level3 = clean_cell_text(row[l3_col]) if l3_col else ""

        # 如果行业列是类似 "银行；股份制银行" 这种多级拼接格式（如同花顺行业）
        if "；" in level1 or ";" in level1:
            parts = level1.replace("；", ";").split(";")
            if len(parts) >= 3:
                level1, level2, level3 = parts[0].strip(), parts[1].strip(), parts[2].strip()
            elif len(parts) == 2:
                level1, level2 = parts[0].strip(), parts[1].strip()
            elif len(parts) == 1:
                level1 = parts[0].strip()

        values = {
                "market_group": market,
                "exchange_suffix": suffix,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "sw_level1_name": level1,
                "sw_level2_name": level2,
                "sw_level3_name": level3,
                "sw_industry_code": industry_code,
        }

        try:
            validated = IndustryRecordInput.model_validate(values)
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

    paths_by_industry_code: dict[str, set[tuple[str, str, str]]] = {}
    for record in records:
        ind_code = str(record["sw_industry_code"])
        if not ind_code:
            continue
        paths_by_industry_code.setdefault(ind_code, set()).add(
            (
                str(record["sw_level1_name"]),
                str(record["sw_level2_name"]),
                str(record["sw_level3_name"]),
            )
        )
    conflicting_codes = {
        code: paths for code, paths in paths_by_industry_code.items() if len(paths) > 1
    }
    for code, paths in sorted(conflicting_codes.items()):
        path_text = "；".join(" / ".join(path) for path in sorted(paths))
        warnings.append(f"行业代码 {code} 对应多个行业路径：{path_text}")

    return ParsedIndustryFile(
        content_hash=content_hash,
        total_rows=len(frame),
        records=records,
        invalid_rows=invalid_rows,
        conflict_rows=len(conflicting_codes),
        warnings=warnings,
    )


# 兼容旧函数签名
def parse_excel(content: bytes) -> ParsedIndustryFile:
    return parse_data(content, "file.xlsx")


def default_source_version(filename: str) -> str:
    return Path(filename).stem[:128]
