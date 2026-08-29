"""新浪个股财务报表接口。"""

import logging
import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pandas as pd

from app.constants.http import SINA_FINANCE_HEADERS
from app.core.market import normalize_code, safe_float

SINA_FINANCIAL_REPORT_URL = (
    "https://quotes.sina.cn/cn/api/openapi.php/"
    "CompanyFinanceService.getFinanceReport2022"
)
SINA_GROSS_REVENUE_URL = (
    "https://quotes.sina.cn/cn/api/openapi.php/"
    "CompanyFinanceService.getGrossRevenue"
)
logger = logging.getLogger(__name__)

_REPORT_SOURCES = {
    "balance": "fzb",
    "profit": "lrb",
    "cashflow": "llb",
}
_FIELD_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "balance": {
        "MONETARYFUNDS": ("CURFDS",),
        "NOTE_ACCOUNTS_RECE": ("NOTESACCORECE",),
        "ACCOUNTS_RECE": ("ACCORECE",),
        "INVENTORY": ("INVE",),
        "TOTAL_CURRENT_ASSETS": ("TOTCURRASSET",),
        "FIXASSET": ("FIXEDASSENET", "FIXEDASSENETW"),
        "INTANGIBLE_ASSET": ("INTAASSET",),
        "GOODWILL": ("GOODWILL",),
        "TOTAL_CURRENT_LIAB": ("TOTALCURRLIAB",),
        "TOTAL_LIABILITIES": ("TOTLIAB",),
        "TOTAL_ASSETS": ("TOTASSET",),
        "TOTAL_EQUITY": ("RIGHAGGR", "TOTSHAREQUI"),
        "TOTAL_PARENT_EQUITY": ("PARESHARRIGH", "PARECOMPSHARRIGHT"),
    },
    "profit": {
        "TOTAL_OPERATE_INCOME": ("BIZTOTINCO",),
        "OPERATE_INCOME": ("BIZINCO",),
        "TOTAL_OPERATE_COST": ("BIZTOTCOST",),
        "OPERATE_COST": ("BIZCOST",),
        "SALE_EXPENSE": ("SALESEXPE",),
        "MANAGE_EXPENSE": ("MANAEXPE",),
        "RESEARCH_EXPENSE": ("DEVEEXPE",),
        "FINANCE_EXPENSE": ("FINEXPE",),
        "OPERATE_PROFIT": ("PERPROFIT", "OPERPROFIT"),
        "NETPROFIT": ("NETPROFIT",),
        "PARENT_NETPROFIT": ("PARENETP", "NETPARECOMPPROF"),
        "BASIC_EPS": ("BASICEPS",),
    },
    "cashflow": {
        "SALES_SERVICES": ("LABORGETCASH",),
        "BUY_SERVICES": ("LABOPAYC",),
        "NETCASH_OPERATE": ("MANANETR",),
        "NETCASH_INVEST": ("INVNETCASHFLOW",),
        "NETCASH_FINANCE": ("FINNETCFLOW",),
        "CCE_ADD": ("CASHNETR",),
    },
}


def _format_period(value: object) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _finite_float(value: object) -> float | None:
    number = safe_float(value)
    if number is not None and not math.isfinite(number):
        raise RuntimeError("新浪财报接口返回非有限数值")
    return number


def _merge_duplicate_value(
    previous: tuple[float | None, float | None] | None,
    value: float | None,
    yoy: float | None,
) -> tuple[float | None, float | None]:
    if previous is None:
        return value, yoy
    previous_value, previous_yoy = previous
    resolved_value = previous_value if previous_value is not None else value
    matching_value = previous_value is None or value is None or value == previous_value
    resolved_yoy = previous_yoy if previous_yoy is not None else yoy if matching_value else None
    return resolved_value, resolved_yoy


def _first_non_null(
    values: Mapping[str, tuple[float | None, float | None]],
    aliases: tuple[str, ...],
) -> tuple[float | None, float | None]:
    for alias in aliases:
        pair = values.get(alias)
        if pair is not None and pair[0] is not None:
            return pair
    return None, None


def _normalize_report_rows(
    report_list: Mapping[str, object],
    report_dates: object,
    indicator: str,
    num: int,
) -> list[dict[str, Any]]:
    aliases = _FIELD_ALIASES[indicator]
    known_fields = {field for fields in aliases.values() for field in fields}
    descriptions = {
        str(item.get("date_value") or "").strip(): str(item.get("date_description") or "").strip()
        for item in report_dates
        if isinstance(item, Mapping) and item.get("date_value")
    } if isinstance(report_dates, list) else {}
    rows: list[dict[str, Any]] = []
    for period in sorted(report_list, reverse=True):
        try:
            datetime.strptime(period, "%Y%m%d")
        except (TypeError, ValueError) as error:
            raise RuntimeError("新浪财报接口返回无效报告期") from error
        report = report_list.get(period)
        if not isinstance(report, Mapping) or not isinstance(report.get("data"), list):
            raise RuntimeError("新浪财报接口返回格式无效")
        values: dict[str, tuple[float | None, float | None]] = {}
        unknown: dict[str, tuple[float | None, float | None]] = {}
        for item in report["data"]:
            if not isinstance(item, Mapping):
                raise RuntimeError("新浪财报接口返回格式无效")
            field = str(item.get("item_field") or "").strip()
            if not field:
                continue
            value = _finite_float(item.get("item_value"))
            yoy = _finite_float(item.get("item_tongbi"))
            target = values if field in known_fields else unknown
            target[field] = _merge_duplicate_value(
                target.get(field),
                value,
                yoy * 100 if yoy is not None else None,
            )

        row: dict[str, Any] = {
            "REPORT_DATE": _format_period(period),
            "REPORT_DATE_NAME": descriptions.get(period) or _format_period(period),
        }
        metadata = {
            "NOTICE_DATE": _format_period(report.get("publish_date")),
            "REPORT_TYPE": str(report.get("rType") or "").strip() or None,
            "CURRENCY": str(report.get("rCurrency") or "").strip() or None,
            "UPDATE_DATE": report.get("update_time"),
        }
        row.update({key: value for key, value in metadata.items() if value is not None})

        recognized = 0
        for canonical, source_fields in aliases.items():
            value, yoy = _first_non_null(values, source_fields)
            if value is None:
                continue
            recognized += 1
            row[canonical] = value
            if yoy is not None:
                row[f"{canonical}_YOY"] = yoy
        if recognized == 0:
            raise RuntimeError("新浪财报接口未返回已识别字段")

        for field, (value, yoy) in unknown.items():
            if value is not None:
                row[field] = value
            if yoy is not None:
                row[f"{field}_YOY"] = yoy
        rows.append(row)
        if len(rows) >= num:
            break
    return rows


def _fetch_report_data(session, paper_code: str, source: str, num: int) -> Mapping[str, object]:
    response = session.get(
        SINA_FINANCIAL_REPORT_URL,
        params={
            "paperCode": paper_code,
            "source": source,
            "type": "0",
            "page": "1",
            "num": str(num),
        },
        headers=SINA_FINANCE_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") if isinstance(payload, Mapping) else None
    status = result.get("status") if isinstance(result, Mapping) else None
    data = result.get("data") if isinstance(result, Mapping) else None
    report_list = data.get("report_list") if isinstance(data, Mapping) else None
    if (
        not isinstance(status, Mapping)
        or status.get("code") != 0
        or not isinstance(report_list, Mapping)
        or not report_list
    ):
        raise RuntimeError("新浪财报接口未返回有效报表")
    return data


def _normalize_deducted_profit_rows(data: Mapping[str, object], num: int) -> dict[str, dict[str, float]]:
    report_list = data.get("report_list")
    if not isinstance(report_list, Mapping):
        raise RuntimeError("新浪财务指标接口返回格式无效")
    result: dict[str, dict[str, float]] = {}
    for period in sorted(report_list, reverse=True)[:num]:
        try:
            datetime.strptime(period, "%Y%m%d")
        except (TypeError, ValueError) as error:
            raise RuntimeError("新浪财务指标接口返回无效报告期") from error
        report = report_list.get(period)
        if not isinstance(report, Mapping) or not isinstance(report.get("data"), list):
            raise RuntimeError("新浪财务指标接口返回格式无效")
        pair: tuple[float | None, float | None] | None = None
        for item in report["data"]:
            if not isinstance(item, Mapping):
                raise RuntimeError("新浪财务指标接口返回格式无效")
            if str(item.get("item_field") or "").strip() != "NPCUT":
                continue
            ratio = _finite_float(item.get("item_tongbi"))
            pair = _merge_duplicate_value(
                pair,
                _finite_float(item.get("item_value")),
                ratio * 100 if ratio is not None else None,
            )
        value, yoy = pair or (None, None)
        fields: dict[str, float] = {}
        if value is not None:
            fields["DEDUCT_PARENT_NETPROFIT"] = value
        if yoy is not None:
            fields["DEDUCT_PARENT_NETPROFIT_YOY"] = yoy
        if fields:
            result[_format_period(period)] = fields
    if not result:
        raise RuntimeError("新浪财务指标接口未返回扣非净利润")
    return result


def _enrich_deducted_profit(
    rows: list[dict[str, Any]],
    supplement: Mapping[str, Mapping[str, float]],
) -> None:
    for row in rows:
        report_date = str(row.get("REPORT_DATE") or "")
        fields = supplement.get(report_date)
        if fields is None:
            continue
        for key, value in fields.items():
            if row.get(key) is None:
                row[key] = value


def _breakdown_number(item: Mapping[str, object], field: str) -> float | None:
    value = item.get(field)
    if type(value) is bool:
        raise RuntimeError(f"新浪营收构成接口包含无效数值: {field}")
    number = _finite_float(value)
    if value not in (None, "", "-", "N/A") and number is None:
        raise RuntimeError(f"新浪营收构成接口包含无效数值: {field}")
    return number


def _normalize_breakdown_item(item: object) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise RuntimeError("新浪营收构成接口返回格式无效")
    class_name = str(item.get("CLASSNAME") or "").strip()
    if not class_name:
        raise RuntimeError("新浪营收构成接口缺少构成项名称")
    revenue = _breakdown_number(item, "TCOREBIZINCOME")
    cost = _breakdown_number(item, "TCOREBIZCOST")
    gross_profit = revenue - cost if revenue is not None and cost is not None else None
    if gross_profit is not None and not math.isfinite(gross_profit):
        raise RuntimeError("新浪营收构成接口包含无效毛利润")
    raw_sub_item = item.get("is_sub_item")
    if raw_sub_item in (True, 1, "1", "true", "True"):
        is_sub_item: bool | None = True
    elif raw_sub_item in (False, 0, "0", "false", "False"):
        is_sub_item = False
    else:
        is_sub_item = None
    return {
        "id": str(item.get("ID") or "").strip() or None,
        "class_name": class_name,
        "is_sub_item": is_sub_item,
        "revenue": revenue,
        "cost": cost,
        "gross_profit": gross_profit,
        "revenue_share_pct": _breakdown_number(item, "COREBIZINCRTO"),
        "gross_margin_pct": _breakdown_number(item, "CLGPMRTO"),
    }


def fetch_revenue_breakdown(session, code: str) -> dict[str, Any]:
    sym = normalize_code(code)
    response = session.get(
        SINA_GROSS_REVENUE_URL,
        params={"paperCode": sym.prefixed_lower},
        headers=SINA_FINANCE_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") if isinstance(payload, Mapping) else None
    status = result.get("status") if isinstance(result, Mapping) else None
    data = result.get("data") if isinstance(result, Mapping) else None
    if not isinstance(status, Mapping) or status.get("code") != 0:
        raise RuntimeError("新浪营收构成接口未返回有效数据")
    if data == []:
        data = {
            "sname": "",
            "by_product": [],
            "by_business": [],
            "by_region": [],
        }
    if not isinstance(data, Mapping):
        raise RuntimeError("新浪营收构成接口未返回有效数据")

    dimensions: dict[str, list[dict[str, Any]]] = {}
    for key in ("by_product", "by_business", "by_region"):
        items = data.get(key)
        if not isinstance(items, list):
            raise RuntimeError("新浪营收构成接口返回格式无效")
        dimensions[key] = [_normalize_breakdown_item(item) for item in items]
    return {
        "code": sym.raw,
        "symbol": sym.prefixed_lower,
        "name": str(data.get("sname") or "").strip(),
        "source": "sina",
        "amount_unit": "CNY_yuan",
        "amount_unit_inferred": True,
        **dimensions,
    }


def fetch_stock_financials(session, code: str, indicator: str, *, num: int = 4) -> pd.DataFrame:
    source = _REPORT_SOURCES.get(indicator)
    if source is None:
        raise ValueError(f"Unknown financial indicator: {indicator}")
    sym = normalize_code(code)
    limit = max(1, num)
    data = _fetch_report_data(session, sym.prefixed_lower, source, limit)
    report_list = data["report_list"]
    if not isinstance(report_list, Mapping):
        raise RuntimeError("新浪财报接口返回格式无效")
    rows = _normalize_report_rows(
        report_list,
        data.get("report_date"),
        indicator,
        limit,
    )
    if not rows:
        raise RuntimeError("新浪财报接口返回格式无效")
    if indicator == "profit":
        try:
            supplement_data = _fetch_report_data(session, sym.prefixed_lower, "gjzb", limit)
            supplement = _normalize_deducted_profit_rows(supplement_data, limit)
        except Exception as error:
            logger.warning(
                "新浪扣非净利润补充不可用: code=%s error_type=%s",
                sym.raw,
                type(error).__name__,
            )
        else:
            _enrich_deducted_profit(rows, supplement)
    return pd.DataFrame(rows)
