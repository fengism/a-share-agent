from __future__ import annotations

import asyncio
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
    if value is None or (isinstance(value, str) and value in ("N/A", "")):
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
    cost = _safe(latest.get("OPERATE_COST"))
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
            "gross_margin": _format_percent(
                round((1 - cost / revenue) * 100, 2) if revenue and cost else None
            ),
            "net_margin": _format_percent(
                round(net_profit / revenue * 100, 2) if net_profit and revenue else None
            ),
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
            "debt_to_asset_ratio": _format_percent(
                round(total_liabilities / total_assets * 100, 2)
                if total_assets and total_liabilities else None
            ),
            "current_ratio": _format_percent(
                round(current_assets / current_liabilities, 2)
                if current_assets and current_liabilities else None
            ),
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
            "cash_quality": _format_percent(
                round(operate_cashflow / sales_cash * 100, 2)
                if operate_cashflow and sales_cash and sales_cash > 0 else None
            ),
        },
        "cashflow_raw": _pick_raw(latest, _CASHFLOW_RAW_FIELDS),
    }


def _build_key_indicators(
    balance: list[dict[str, Any]],
    profit: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    if not metrics:
        return {}
    metric_values = _as_mapping(metrics.get("metrics"))
    profit_row = _latest_row(profit)
    balance_row = _latest_row(balance)
    net_profit = _safe(profit_row.get("PARENT_NETPROFIT"))
    revenue = _safe(profit_row.get("OPERATE_INCOME"))
    cost = _safe(profit_row.get("TOTAL_OPERATE_COST"))
    total_assets = _safe(balance_row.get("TOTAL_ASSETS"))
    parent_equity = _safe(balance_row.get("TOTAL_PARENT_EQUITY"))
    debt_to_asset = metric_values.get("资产负债率")
    return {
        "key_indicators": {
            "roe": _format_percent(
                round(net_profit / parent_equity * 100, 2)
                if net_profit and parent_equity else None
            ),
            "roa": _format_percent(
                round(net_profit / total_assets * 100, 2)
                if net_profit and total_assets else None
            ),
            "gross_margin": _format_percent(
                round((1 - cost / revenue) * 100, 2) if revenue and cost else None
            ),
            "net_margin": _format_percent(
                round(net_profit / revenue * 100, 2) if net_profit and revenue else None
            ),
            "debt_to_asset": _format_percent(
                round(debt_to_asset * 100, 2) if debt_to_asset else None
            ),
        }
    }


async def analyze_financials(code: str) -> Any:
    gathered = cast(
        tuple[Any, Any, Any, Any],
        await asyncio.gather(
            helpers.get_stock_financial(code, indicator="balance"),
            helpers.get_stock_financial(code, indicator="profit"),
            helpers.get_stock_financial(code, indicator="cashflow"),
            helpers.get_stock_financial_metrics(code),
            return_exceptions=True,
        ),
    )
    balance_value, profit_value, cashflow_value, metrics_value = gathered
    balance = _as_rows(balance_value)
    profit = _as_rows(profit_value)
    cashflow = _as_rows(cashflow_value)
    metrics = _as_mapping(metrics_value)
    result: dict[str, Any] = {"code": code}

    if balance:
        result["report_date"] = str(_safe(balance[0].get("REPORT_DATE_NAME"), ""))
    elif metrics:
        result["report_date"] = metrics.get("latest_report_date", "")

    result.update(_build_income_sections(profit))
    result.update(_build_balance_sections(balance))
    result.update(_build_cashflow_sections(cashflow))
    result.update(_build_key_indicators(balance, profit, metrics))
    return result
