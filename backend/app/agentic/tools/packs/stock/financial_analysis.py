from __future__ import annotations

import asyncio
import math
from typing import Any, cast

from app.agentic.tools.packs.stock import helpers
from app.constants.financial_labels import FINANCIAL_RAW_FIELD_LABELS

_INCOME_RAW_FIELDS = (
    "TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "OPERATE_INCOME_YOY",
    "OPERATE_COST", "TOTAL_OPERATE_COST",
    "SALE_EXPENSE", "MANAGE_EXPENSE", "RESEARCH_EXPENSE", "FINANCE_EXPENSE",
    "OPERATE_PROFIT", "OPERATE_PROFIT_YOY",
    "PARENT_NETPROFIT", "PARENT_NETPROFIT_YOY",
    "DEDUCT_PARENT_NETPROFIT", "DEDUCT_PARENT_NETPROFIT_YOY",
    "BASIC_EPS",
)
_BALANCE_RAW_FIELDS = (
    "TOTAL_ASSETS", "TOTAL_CURRENT_ASSETS", "MONETARYFUNDS",
    "NOTE_ACCOUNTS_RECE", "ACCOUNTS_RECE", "INVENTORY",
    "FIXASSET", "INTANGIBLE_ASSET", "GOODWILL",
    "TOTAL_CURRENT_LIAB", "TOTAL_LIABILITIES",
    "TOTAL_EQUITY", "TOTAL_PARENT_EQUITY",
)
_CASHFLOW_RAW_FIELDS = (
    "NETCASH_OPERATE", "NETCASH_OPERATE_YOY",
    "SALES_SERVICES", "BUY_SERVICES",
    "NETCASH_INVEST", "NETCASH_FINANCE", "CCE_ADD",
)


def _safe(value, default=None):
    if isinstance(value, Exception):
        return default
    if value is None or isinstance(value, bool) or (isinstance(value, str) and value in ("N/A", "")):
        return default
    if isinstance(value, (int, float)) and not math.isfinite(value):
        return default
    return value


def _format_amount(value):
    if value is None:
        return None
    return round(value / 1e8, 2)


def _format_percent(value):
    if value is None:
        return None
    return round(value, 2)


def _ratio(numerator, denominator, *, percent: bool = True):
    numerator, denominator = _safe(numerator), _safe(denominator)
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * (100 if percent else 1), 2)


def _gross_margin(row: dict) -> float | None:
    # Total operating cost includes period expenses and is NOT cost of revenue.
    revenue, cost = _safe(row.get("OPERATE_INCOME")), _safe(row.get("OPERATE_COST"))
    if revenue is None or cost is None or revenue <= 0:
        return None
    return float(round((revenue - cost) / revenue * 100, 2))


def _report_metadata(rows: list[dict]) -> dict[str, str | None]:
    row = _latest_row(rows)
    return {
        "report_date": str(row.get("REPORT_DATE") or row.get("REPORT_DATE_NAME") or "") or None,
        "report_label": str(row.get("REPORT_DATE_NAME") or "") or None,
        "currency": str(row.get("CURRENCY") or "").strip() or None,
    }


def _compatible_reports(left: list[dict], right: list[dict]) -> bool:
    a, b = _report_metadata(left), _report_metadata(right)
    return bool(a["report_date"] and a["report_date"] == b["report_date"]
                and a["currency"] and a["currency"] == b["currency"])


def _latest_row(data):
    if isinstance(data, list) and data:
        return data[0]
    return {}


def _pick_raw(row: dict, keys: tuple[str, ...]) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for key in keys:
        value = _safe(row.get(key))
        if value is not None:
            raw[FINANCIAL_RAW_FIELD_LABELS.get(key, key)] = value
    return raw


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _build_income_sections(profit: list[dict[str, Any]]) -> dict[str, Any]:
    if not profit:
        return {}
    latest = _latest_row(profit)
    revenue = _safe(latest.get("OPERATE_INCOME"))
    net_profit = _safe(latest.get("PARENT_NETPROFIT"))
    operate_profit = _safe(latest.get("OPERATE_PROFIT"))
    eps = _safe(latest.get("BASIC_EPS"))

    revenue_trend = []
    profit_trend = []
    for row in profit[:4]:
        period = _safe(row.get("REPORT_DATE_NAME"), "")
        if not period:
            continue
        revenue_trend.append({
            "period": period,
            "revenue_billion": _format_amount(_safe(row.get("OPERATE_INCOME"))),
        })
        profit_trend.append({
            "period": period,
            "net_profit_billion": _format_amount(_safe(row.get("PARENT_NETPROFIT"))),
        })
    return {
        "income": {
            "revenue_billion": _format_amount(revenue),
            "revenue_yoy": _format_percent(_safe(latest.get("OPERATE_INCOME_YOY"))),
            "operating_profit_billion": _format_amount(operate_profit),
            "net_profit_billion": _format_amount(net_profit),
            "net_profit_yoy": _format_percent(_safe(latest.get("PARENT_NETPROFIT_YOY"))),
            "gross_margin": _gross_margin(latest),
            "net_margin": _ratio(net_profit, revenue),
            "eps": eps,
        },
        "income_raw": _pick_raw(latest, _INCOME_RAW_FIELDS),
        "revenue_trend": revenue_trend,
        "profit_trend": profit_trend,
    }


def _build_balance_sections(balance: list[dict[str, Any]]) -> dict[str, Any]:
    if not balance:
        return {}
    latest = _latest_row(balance)
    total_assets = _safe(latest.get("TOTAL_ASSETS"))
    total_liabilities = _safe(latest.get("TOTAL_LIABILITIES"))
    total_equity = _safe(latest.get("TOTAL_EQUITY"))
    cash = _safe(latest.get("MONETARYFUNDS"))
    inventory = _safe(latest.get("INVENTORY"))
    current_assets = _safe(latest.get("TOTAL_CURRENT_ASSETS"))
    current_liabilities = _safe(latest.get("TOTAL_CURRENT_LIAB"))
    return {
        "balance": {
            "total_assets_billion": _format_amount(total_assets),
            "total_liabilities_billion": _format_amount(total_liabilities),
            "total_equity_billion": _format_amount(total_equity),
            "cash_billion": _format_amount(cash),
            "inventory_billion": _format_amount(inventory),
            "debt_to_asset_ratio": _ratio(total_liabilities, total_assets),
            "current_ratio": _ratio(current_assets, current_liabilities, percent=False),
        },
        "balance_raw": _pick_raw(latest, _BALANCE_RAW_FIELDS),
    }


def _build_cashflow_sections(cashflow: list[dict[str, Any]]) -> dict[str, Any]:
    if not cashflow:
        return {}
    latest = _latest_row(cashflow)
    operate_cashflow = _safe(latest.get("NETCASH_OPERATE"))
    invest_cashflow = _safe(latest.get("NETCASH_INVEST"))
    finance_cashflow = _safe(latest.get("NETCASH_FINANCE"))
    sales_cash = _safe(latest.get("SALES_SERVICES"))
    return {
        "cashflow": {
            "operate_cashflow_billion": _format_amount(operate_cashflow),
            "operate_cf_yoy": _format_percent(_safe(latest.get("NETCASH_OPERATE_YOY"))),
            "invest_cashflow_billion": _format_amount(invest_cashflow),
            "finance_cashflow_billion": _format_amount(finance_cashflow),
            "free_cashflow_billion": _format_amount(
                operate_cashflow + invest_cashflow
                if operate_cashflow is not None and invest_cashflow is not None else None
            ),
            "sales_cash_billion": _format_amount(sales_cash),
            "cash_quality": _ratio(operate_cashflow, sales_cash),
        },
        "cashflow_raw": _pick_raw(latest, _CASHFLOW_RAW_FIELDS),
    }


def _build_key_indicators(
    balance: list[dict[str, Any]],
    profit: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    profit_row = _latest_row(profit)
    balance_row = _latest_row(balance)
    aligned = _compatible_reports(balance, profit)
    return {
        "key_indicators": {
            "roe": _ratio(profit_row.get("PARENT_NETPROFIT"), balance_row.get("TOTAL_PARENT_EQUITY")) if aligned else None,
            "roa": _ratio(profit_row.get("PARENT_NETPROFIT"), balance_row.get("TOTAL_ASSETS")) if aligned else None,
            "gross_margin": _gross_margin(profit_row),
            "net_margin": _ratio(profit_row.get("PARENT_NETPROFIT"), profit_row.get("OPERATE_INCOME")),
            "debt_to_asset": _ratio(balance_row.get("TOTAL_LIABILITIES"), balance_row.get("TOTAL_ASSETS")),
        }
    }


def _compact_revenue_breakdown(value: Any) -> dict[str, Any]:
    if isinstance(value, Exception) or not isinstance(value, dict):
        return {"status": "unavailable"}
    dimensions = {}
    for source_key, target_key in (
        ("by_product", "product"),
        ("by_business", "business"),
        ("by_region", "region"),
    ):
        source_items = value.get(source_key)
        items = source_items if isinstance(source_items, list) else []
        compact_items = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            compact_items.append({
                key: item[key]
                for key in (
                    "class_name", "is_sub_item", "revenue", "cost", "gross_profit",
                    "revenue_share_pct", "gross_margin_pct",
                )
                if item.get(key) is not None
            })
        dimensions[target_key] = {
            "total_items": len(items),
            "returned_items": len(compact_items),
            "truncated": len(items) > len(compact_items),
            "items": compact_items,
        }
    status = "available" if any(dimension["total_items"] for dimension in dimensions.values()) else "empty"
    return {
        "status": status,
        "source": "sina",
        "report_date": None,
        "amount_unit": value.get("amount_unit", "CNY_yuan"),
        "amount_unit_inferred": bool(value.get("amount_unit_inferred", True)),
        "dimensions": dimensions,
        "caveats": ["上游未提供报告期", "不同维度或条目可能重叠，不可直接加总"],
    }


async def analyze_financials(code: str) -> Any:
    gathered = cast(
        tuple[Any, Any, Any, Any, Any],
        await asyncio.gather(
            helpers.get_stock_financial(code, indicator="balance"),
            helpers.get_stock_financial(code, indicator="profit"),
            helpers.get_stock_financial(code, indicator="cashflow"),
            helpers.get_stock_financial_metrics(code),
            helpers.get_stock_revenue_breakdown(code),
            return_exceptions=True,
        ),
    )
    balance_value, profit_value, cashflow_value, metrics_value, breakdown_value = gathered
    balance = _as_rows(balance_value)
    profit = _as_rows(profit_value)
    cashflow = _as_rows(cashflow_value)
    metrics = _as_mapping(metrics_value)
    result: dict[str, Any] = {"code": code}

    report_metadata = {key: _report_metadata(rows) for key, rows in (
        ("income", profit), ("balance", balance), ("cashflow", cashflow),
    )}
    result["report_date"] = report_metadata["income"]["report_label"] or report_metadata["income"]["report_date"]
    result["report_metadata"] = report_metadata
    result["amount_units"] = {
        "legacy_billion_fields_divisor": 100_000_000,
        "legacy_billion_fields_unit": "亿（各报表原币种），不是十亿",
        "currency_by_section": {key: meta["currency"] for key, meta in report_metadata.items()},
        "currency_missing_policy": "币种缺失时不推断为人民币，不进行跨表金额比率计算",
    }
    result.update(_build_income_sections(profit))
    result.update(_build_balance_sections(balance))
    result.update(_build_cashflow_sections(cashflow))
    result.update(_build_key_indicators(balance, profit, metrics))
    result["revenue_breakdown"] = _compact_revenue_breakdown(breakdown_value)
    # 保留失败原因的类型名：全部上游挂掉时要能让调用方与日志区分「限流」「解析失败」
    # 还是「代码不存在」，否则只能看到一个笼统的空结果。
    upstream_errors = {
        name: type(value).__name__
        for name, value in (
            ("balance", balance_value),
            ("profit", profit_value),
            ("cashflow", cashflow_value),
            ("metrics", metrics_value),
            ("revenue_breakdown", breakdown_value),
        )
        if isinstance(value, Exception)
    }
    unavailable_sections = [
        name
        for name, value in (
            ("balance", balance_value),
            ("profit", profit_value),
            ("cashflow", cashflow_value),
            ("metrics", metrics_value),
            ("revenue_breakdown", breakdown_value),
        )
        if isinstance(value, Exception) or not value
    ]
    result["partial"] = bool(unavailable_sections)
    result["unavailable_sections"] = unavailable_sections
    core_sections = {
        "balance": bool(balance),
        "profit": bool(profit),
        "cashflow": bool(cashflow),
        "metrics": bool(metrics),
    }
    dates = [meta["report_date"] for meta in report_metadata.values()]
    common_date = dates[0] if all(dates) and len(set(dates)) == 1 else None
    warnings = ["营收与毛利构成上游未提供报告期"] if result["revenue_breakdown"]["status"] == "available" else []
    if common_date is None:
        warnings.append("三张报表报告期不齐或不同；各节保留自身口径，不宣称统一报告期")
    if not _compatible_reports(balance, profit):
        warnings.append("利润表与资产负债表日期/币种不齐或不一致，ROE/ROA未计算")
    warnings.append("ROE/ROA为同期间利润除以期末权益/资产，未年化且未使用期初期末平均值")
    result["data_quality"] = {
        "core_sections": core_sections,
        "common_report_date": common_date,
        "revenue_breakdown_status": result["revenue_breakdown"]["status"],
        "partial": bool(unavailable_sections),
        "unavailable_sections": unavailable_sections,
        "warnings": warnings,
    }
    if upstream_errors:
        result["upstream_errors"] = upstream_errors

    # 核心分片（三张表 + 关键指标）全部拿不到时，必须返回错误而不是成功。
    # 此前这里无条件返回 ok:true + 全 null：Agent 看到「调用成功」就不会换工具，
    # 而产业链的证据校验又要求 report_date 与利润表数值，于是判定证据缺失 ->
    # 修复循环用同样参数反复重调 -> 一直失败到 max_rounds 耗尽。
    # revenue_breakdown 不计入核心：新浪 getGrossRevenue 常年为空属正常，
    # 不能因为它缺就把整次调用判死。
    if not any(core_sections.values()):
        failed = sorted(name for name, ok in core_sections.items() if not ok)
        causes = "、".join(f"{name}:{upstream_errors[name]}" for name in failed if name in upstream_errors)
        result["error_code"] = "upstream_unavailable"
        result["error"] = (
            f"{code} 的三张报表与关键指标全部取不到（{', '.join(failed)}）"
            + (f"；上游原因 {causes}" if causes else "；上游返回空数据")
            + "。这是数据源暂时不可用，不是该公司没有财务数据。"
            "请改用其他来源（如 get_stock_financial、get_stock_valuation_detail、"
            "iwencai_search 或 web_search）获取，不要用相同参数重复调用本工具。"
        )
    return result
