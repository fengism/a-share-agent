"""同花顺港股 F10 财务报表与核心指标解析。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from bs4 import BeautifulSoup

from app.core.market import is_hk_code
from app.infrastructure.providers.ths.hk_f10 import fetch_ths_f10_page
from app.infrastructure.providers.ths.transport import ThsTransport

_BLOCK_BY_INDICATOR = {
    "balance": "debt",
    "profit": "benefit",
    "cashflow": "cash",
    "metrics": "keyindex",
}

# 同时保留同花顺的中文原始科目，并补充项目统一字段，供既有财报展示和指标汇总复用。
_STANDARD_FIELDS = {
    "balance": {
        "资产合计": "TOTAL_ASSETS",
        "负债合计": "TOTAL_LIABILITIES",
        "权益合计": "TOTAL_EQUITY",
        "归属于母公司股东权益": "TOTAL_PARENT_EQUITY",
        "流动资产": "TOTAL_CURRENT_ASSETS",
        "流动负债": "TOTAL_CURRENT_LIAB",
        "货币资金": "MONETARYFUNDS",
        "现金及现金等价物": "MONETARYFUNDS",
        "应收账款及票据": "NOTE_ACCOUNTS_RECE",
        "存货": "INVENTORY",
    },
    "profit": {
        "营业收入": "OPERATE_INCOME",
        "销售成本": "OPERATE_COST",
        "经营溢利": "OPERATE_PROFIT",
        "税后利润": "NETPROFIT",
        "归属于母公司股东利润": "PARENT_NETPROFIT",
        "基本每股收益": "BASIC_EPS",
        "稀释每股收益": "DILUTED_EPS",
    },
    "cashflow": {
        "经营活动现金流量净额": "NETCASH_OPERATE",
        "投资活动现金流量净额": "NETCASH_INVEST",
        "融资活动现金流量净额": "NETCASH_FINANCE",
        "现金及现金等价物净增加额": "NET_INCREASE_CASH",
        "现金及现金等价物期末余额": "ENDING_CASH",
    },
}

_METRIC_NAMES = {
    "营业收入": "营收",
    "归母净利润": "净利润",
    "毛利": "毛利",
    "营业利润率": "营业利润率",
    "资产合计": "总资产",
    "流动资产": "流动资产",
    "非流动资产": "非流动资产",
    "净资产收益率": "净资产收益率",
    "资产负债率": "资产负债率",
    "负债和股东权益总计": "负债和股东权益总计",
    "负债合计": "总负债",
    "权益合计": "股东权益",
    "每股收益-基本": "基本每股收益",
    "每股收益-稀释": "稀释每股收益",
    "每股营业总收入": "每股营业总收入",
    "每股净资产": "每股净资产",
    "每股公积金": "每股公积金",
    "每股现金流": "每股现金流",
}

_EMPTY_VALUES = frozenset({"", "--", "-", "N/A", "null", "None"})
_NUMERIC_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_HK_CODE_PATTERN = re.compile(r"^(?:hk)?(\d{1,5})$", re.IGNORECASE)


def _normalize_hk_code(code: str) -> str:
    match = _HK_CODE_PATTERN.fullmatch(str(code or "").strip())
    if match is None:
        raise ValueError("同花顺港股财务仅支持港股代码")
    return match.group(1).zfill(5)


def _load_block(soup: BeautifulSoup, block_id: str) -> Mapping[str, Any]:
    node = soup.find("p", id=block_id)
    if node is None:
        raise ValueError(f"同花顺港股财务页面缺少数据块: {block_id}")
    raw = node.get_text(strip=True)
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"同花顺港股财务数据块格式异常: {block_id}") from error
    if not isinstance(payload, Mapping):
        raise ValueError(f"同花顺港股财务数据块不是对象: {block_id}")
    return payload


def _parse_value(value: object) -> float | str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if text in _EMPTY_VALUES:
        return None
    numeric = text.replace(",", "").replace("，", "")
    if numeric.endswith("%"):
        numeric = numeric[:-1].strip()
    if _NUMERIC_PATTERN.fullmatch(numeric):
        return float(numeric)
    return text


def _title_parts(title: object) -> tuple[str, str, str]:
    if not isinstance(title, Sequence) or isinstance(title, (str, bytes)) or not title:
        return "", "", ""
    name = str(title[0]).strip().lstrip("*").strip()
    unit = str(title[1]).strip() if len(title) > 1 else ""
    kind = str(title[2]).strip() if len(title) > 2 else ""
    return name, unit, kind


def _normalize_period(period: object, end_date: object | None) -> str:
    text = str(period).strip()
    if re.fullmatch(r"\d{4}", text):
        suffix = str(end_date or "12-31").strip()
        if not re.fullmatch(r"\d{2}-\d{2}", suffix):
            suffix = "12-31"
        return f"{text}-{suffix}"
    return text


def parse_hk_finance_block(
    soup: BeautifulSoup,
    block_id: str,
    *,
    period_type: str = "report",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """解析一个内嵌财务 JSON 块，按报告期输出行记录。"""
    if period_type not in {"report", "year"}:
        raise ValueError(f"不支持的港股财务周期类型: {period_type}")
    if limit is not None and limit <= 0:
        raise ValueError("港股财务记录数必须大于 0")

    payload = _load_block(soup, block_id)
    titles = payload.get("title")
    matrix = payload.get(period_type)
    if not isinstance(titles, list) or not isinstance(matrix, list) or not matrix:
        raise ValueError(f"同花顺港股财务数据块结构异常: {block_id}")
    if not isinstance(matrix[0], list):
        raise ValueError(f"同花顺港股财务报告期结构异常: {block_id}")

    end_dates = matrix[1] if len(matrix) > 1 and isinstance(matrix[1], list) else []
    periods = [
        _normalize_period(period, end_dates[index] if index < len(end_dates) else None)
        for index, period in enumerate(matrix[0])
    ]
    records: list[dict[str, Any]] = [
        {"REPORT_DATE": period, "REPORT_DATE_NAME": period, "SOURCE": "ths"} for period in periods
    ]
    units: dict[str, str] = {}

    for row_index, title in enumerate(titles[1:], start=1):
        name, unit, kind = _title_parts(title)
        if not name or kind == "TN":
            continue
        if row_index >= len(matrix) or not isinstance(matrix[row_index], list):
            continue
        values = matrix[row_index]
        if unit:
            units[name] = unit
        for period_index, record in enumerate(records):
            value = _parse_value(values[period_index]) if period_index < len(values) else None
            # 页面同时给出“核心指标”和“全部指标”，名称会在去星号后重复；
            # 后一行为空时不能覆盖前面已经披露的有效值。
            if name not in record or value is not None:
                record[name] = value

    indicator = next((key for key, value in _BLOCK_BY_INDICATOR.items() if value == block_id), None)
    if indicator in _STANDARD_FIELDS:
        for record in records:
            for raw_name, standard_name in _STANDARD_FIELDS[indicator].items():
                if raw_name in record and standard_name not in record:
                    record[standard_name] = record[raw_name]
    for record in records:
        record["CURRENCY"] = record.get("原始货币")
        record["AUDIT_OPINION"] = record.get("审计意见")
        if units:
            record["__units__"] = units.copy()

    return records[:limit] if limit is not None else records


def fetch_hk_financial_statement(
    transport: ThsTransport,
    code: str,
    indicator: str,
    *,
    period_type: str = "report",
    limit: int = 4,
) -> list[dict[str, Any]]:
    """获取港股资产负债表、利润表或现金流量表。"""
    if not is_hk_code(code):
        raise ValueError("同花顺港股财务仅支持港股代码")
    if indicator not in {"balance", "profit", "cashflow"}:
        raise ValueError(f"不支持的港股财报类型: {indicator}")
    soup = fetch_ths_f10_page(transport, _normalize_hk_code(code), "finance.html")
    records = parse_hk_finance_block(
        soup,
        _BLOCK_BY_INDICATOR[indicator],
        period_type=period_type,
        limit=limit,
    )
    # 单位映射仅用于 Provider 内部判定百分比，不作为报表科目暴露给 API。
    for record in records:
        record.pop("__units__", None)
    return records


def fetch_hk_financial_metrics(transport: ThsTransport, code: str) -> dict[str, Any]:
    """获取港股最新一期核心财务指标。百分比转换为 0-1 比率以兼容既有接口。"""
    if not is_hk_code(code):
        raise ValueError("同花顺港股财务仅支持港股代码")
    hk_code = _normalize_hk_code(code)
    soup = fetch_ths_f10_page(transport, hk_code, "finance.html")
    rows = parse_hk_finance_block(soup, _BLOCK_BY_INDICATOR["metrics"], limit=1)
    if not rows:
        return {"code": hk_code, "latest_report_date": None, "metrics": {}}
    row = rows[0]
    units = row.get("__units__", {})
    metrics: dict[str, float | None] = {}
    for raw_name, output_name in _METRIC_NAMES.items():
        value = row.get(raw_name)
        numeric = value if isinstance(value, float) else None
        if numeric is not None and isinstance(units, Mapping) and units.get(raw_name) == "%":
            numeric = numeric / 100
        metrics[output_name] = numeric
    return {
        "code": hk_code,
        "latest_report_date": row.get("REPORT_DATE"),
        "metrics": metrics,
    }


__all__ = [
    "fetch_hk_financial_metrics",
    "fetch_hk_financial_statement",
    "parse_hk_finance_block",
]
