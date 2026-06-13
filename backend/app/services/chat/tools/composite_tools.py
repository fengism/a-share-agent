from __future__ import annotations

import asyncio
from typing import Any

from app.services.chat.tools import stock_helpers as helpers
from app.services.chat.tools.registry import Tool, registry


async def _gather_labeled(tasks: dict[str, Any]) -> dict[str, Any]:
    """并行执行一组带标签的协程任务，异常转为 error 字符串。

    Param:
        tasks: 任务名到协程的映射字典
    Return:
        任务名到结果的字典，异常任务的结果为 {"error": str(exc)}
    """
    labels = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {
        label: {"error": str(result)} if isinstance(result, Exception) else result
        for label, result in zip(labels, results)
    }


async def _analyze_stock(code: str) -> Any:
    """组合技能：一键获取个股全维度数据（信息+估值+技术+新闻+情绪）。"""
    return {
        "code": code,
        **await _gather_labeled({
            "info": helpers.get_stock_info(code),
            "valuation": helpers.get_stock_valuation_detail(code),
            "technical": helpers.get_stock_technical_indicators(code),
            "news": helpers.get_stock_news(code),
            "sentiment": helpers.get_stock_sentiment(code),
        }),
    }


async def _sector_analysis(name: str) -> Any:
    """组合技能：行业分析（热门排名+行业筛选+相关研报）。"""
    return {
        "industry": name,
        **await _gather_labeled({
            "hot_industries": _get_hot_rank("industries"),
            "stocks": helpers.screen_stocks(industries=[name], page=1, page_size=15),
            "reports": helpers.iwencai_search(f"{name} 行业 研报", "report", 10),
        }),
    }


async def _get_hot_rank(type: str = "industries") -> Any:
    """获取热门排名数据，根据 type 返回热门概念/行业/股票。

    Param:
        type: 热门类型，concepts=热门概念，industries=热门行业，其他=热门股票
    Return:
        对应类型的热门排名数据
    """
    from app.services.market.hot_rank import get_hot_stocks, get_ths_hot_concept, get_ths_hot_industry
    if type == "concepts":
        return await get_ths_hot_concept()
    if type == "industries":
        return await get_ths_hot_industry()
    return await get_hot_stocks()


async def _compare_stocks(codes: str) -> Any:
    """组合技能：多股对比分析。codes 为逗号分隔的股票代码。"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) > 5:
        return {"error": "最多对比5只股票"}
    if not code_list:
        return {"error": "请输入至少一个股票代码"}

    async def fetch_one(code: str) -> dict:
        info, valuation = await asyncio.gather(
            helpers.get_stock_info(code),
            helpers.get_stock_valuation_detail(code),
            return_exceptions=True,
        )
        result = {"code": code}
        result["info"] = {"error": str(info)} if isinstance(info, Exception) else info
        result["valuation"] = (
            {"error": str(valuation)} if isinstance(valuation, Exception) else valuation
        )
        return result

    results = await asyncio.gather(*[fetch_one(c) for c in code_list])
    return {"comparison": results}


async def _analyze_financials(code: str) -> Any:
    """组合技能：一键获取个股财报分析（三张报表 + 关键指标 + 原始数据 + 趋势分析）。"""
    from app.constants.financial_labels import FINANCIAL_RAW_FIELD_LABELS

    balance, profit, cashflow, metrics = await asyncio.gather(
        helpers.get_stock_financial(code, indicator="balance"),
        helpers.get_stock_financial(code, indicator="profit"),
        helpers.get_stock_financial(code, indicator="cashflow"),
        helpers.get_stock_financial_metrics(code),
        return_exceptions=True,
    )

    def _safe(val, default=None):
        if isinstance(val, Exception):
            return default
        if val is None or (isinstance(val, str) and val in ("N/A", "")):
            return default
        return val

    def _fmt_amount(val):
        if val is None:
            return None
        return round(val / 1e8, 2)

    def _fmt_pct(val):
        if val is None:
            return None
        return round(val, 2)

    def _latest_row(data):
        if isinstance(data, list) and data:
            return data[0]
        return {}

    def _pick_raw(row: dict, keys: tuple[str, ...]) -> dict[str, Any]:
        """从原始数据行中提取指定字段的原始值，用中文标签做 key。"""
        raw: dict[str, Any] = {}
        for key in keys:
            val = _safe(row.get(key))
            if val is not None:
                label = FINANCIAL_RAW_FIELD_LABELS.get(key, key)
                raw[label] = val
        return raw

    result: dict[str, Any] = {"code": code}

    # ── 基本信息 ──
    if isinstance(balance, list) and balance:
        result["report_date"] = str(_safe(balance[0].get("REPORT_DATE_NAME"), ""))
    elif isinstance(metrics, dict):
        result["report_date"] = metrics.get("latest_report_date", "")

    # ── 利润表分析 ──
    if not isinstance(profit, Exception) and profit:
        latest = _latest_row(profit)
        revenue = _safe(latest.get("OPERATE_INCOME"))
        cost = _safe(latest.get("OPERATE_COST"))
        net_profit = _safe(latest.get("PARENT_NETPROFIT"))
        operate_profit = _safe(latest.get("OPERATE_PROFIT"))
        eps = _safe(latest.get("BASIC_EPS"))

        result["income"] = {
            "revenue_billion": _fmt_amount(revenue),
            "revenue_yoy": _fmt_pct(_safe(latest.get("OPERATE_INCOME_YOY"))),
            "operating_profit_billion": _fmt_amount(operate_profit),
            "net_profit_billion": _fmt_amount(net_profit),
            "net_profit_yoy": _fmt_pct(_safe(latest.get("PARENT_NETPROFIT_YOY"))),
            "gross_margin": _fmt_pct(
                round((1 - cost / revenue) * 100, 2) if revenue and cost else None
            ),
            "net_margin": _fmt_pct(
                round(net_profit / revenue * 100, 2) if net_profit and revenue else None
            ),
            "eps": eps,
        }

        result["income_raw"] = _pick_raw(latest, (
            "TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "OPERATE_INCOME_YOY",
            "OPERATE_COST", "TOTAL_OPERATE_COST",
            "SALE_EXPENSE", "MANAGE_EXPENSE", "RESEARCH_EXPENSE", "FINANCE_EXPENSE",
            "OPERATE_PROFIT", "OPERATE_PROFIT_YOY",
            "PARENT_NETPROFIT", "PARENT_NETPROFIT_YOY",
            "DEDUCT_PARENT_NETPROFIT", "DEDUCT_PARENT_NETPROFIT_YOY",
            "BASIC_EPS",
        ))

        # 趋势：最近 4 期营收和净利润
        revenue_trend = []
        profit_trend = []
        for row in profit[:4]:
            name = _safe(row.get("REPORT_DATE_NAME"), "")
            rev = _safe(row.get("OPERATE_INCOME"))
            np_ = _safe(row.get("PARENT_NETPROFIT"))
            if name:
                revenue_trend.append({"period": name, "revenue_billion": _fmt_amount(rev)})
                profit_trend.append({"period": name, "net_profit_billion": _fmt_amount(np_)})
        result["revenue_trend"] = revenue_trend
        result["profit_trend"] = profit_trend

    # ── 资产负债表分析 ──
    if not isinstance(balance, Exception) and balance:
        latest = _latest_row(balance)
        total_assets = _safe(latest.get("TOTAL_ASSETS"))
        total_liab = _safe(latest.get("TOTAL_LIABILITIES"))
        total_equity = _safe(latest.get("TOTAL_EQUITY"))
        cash = _safe(latest.get("MONETARYFUNDS"))
        inventory = _safe(latest.get("INVENTORY"))
        current_assets = _safe(latest.get("TOTAL_CURRENT_ASSETS"))
        current_liab = _safe(latest.get("TOTAL_CURRENT_LIAB"))

        result["balance"] = {
            "total_assets_billion": _fmt_amount(total_assets),
            "total_liabilities_billion": _fmt_amount(total_liab),
            "total_equity_billion": _fmt_amount(total_equity),
            "cash_billion": _fmt_amount(cash),
            "inventory_billion": _fmt_amount(inventory),
            "debt_to_asset_ratio": _fmt_pct(
                round(total_liab / total_assets * 100, 2) if total_assets and total_liab else None
            ),
            "current_ratio": _fmt_pct(
                round(current_assets / current_liab, 2) if current_assets and current_liab else None
            ),
        }

        result["balance_raw"] = _pick_raw(latest, (
            "TOTAL_ASSETS", "TOTAL_CURRENT_ASSETS", "MONETARYFUNDS",
            "NOTE_ACCOUNTS_RECE", "ACCOUNTS_RECE", "INVENTORY",
            "FIXASSET", "INTANGIBLE_ASSET", "GOODWILL",
            "TOTAL_CURRENT_LIAB", "TOTAL_LIABILITIES",
            "TOTAL_EQUITY", "TOTAL_PARENT_EQUITY",
        ))

    # ── 现金流量表分析 ──
    if not isinstance(cashflow, Exception) and cashflow:
        latest = _latest_row(cashflow)
        operate_cf = _safe(latest.get("NETCASH_OPERATE"))
        invest_cf = _safe(latest.get("NETCASH_INVEST"))
        finance_cf = _safe(latest.get("NETCASH_FINANCE"))
        sales_cash = _safe(latest.get("SALES_SERVICES"))

        result["cashflow"] = {
            "operate_cashflow_billion": _fmt_amount(operate_cf),
            "operate_cf_yoy": _fmt_pct(_safe(latest.get("NETCASH_OPERATE_YOY"))),
            "invest_cashflow_billion": _fmt_amount(invest_cf),
            "finance_cashflow_billion": _fmt_amount(finance_cf),
            "free_cashflow_billion": _fmt_amount(
                operate_cf + invest_cf if operate_cf is not None and invest_cf is not None else None
            ),
            "sales_cash_billion": _fmt_amount(sales_cash),
            "cash_quality": _fmt_pct(
                round(operate_cf / sales_cash * 100, 2) if operate_cf and sales_cash and sales_cash > 0 else None
            ),
        }

        result["cashflow_raw"] = _pick_raw(latest, (
            "NETCASH_OPERATE", "NETCASH_OPERATE_YOY",
            "SALES_SERVICES", "BUY_SERVICES",
            "NETCASH_INVEST", "NETCASH_FINANCE",
            "CCE_ADD",
        ))

    # ── 关键指标汇总 ──
    if isinstance(metrics, dict):
        m = metrics.get("metrics", {})
        net_profit = None
        revenue = None
        if isinstance(profit, list) and profit:
            net_profit = _safe(profit[0].get("PARENT_NETPROFIT"))
            revenue = _safe(profit[0].get("OPERATE_INCOME"))
        total_assets = None
        parent_equity = None
        if isinstance(balance, list) and balance:
            total_assets = _safe(balance[0].get("TOTAL_ASSETS"))
            parent_equity = _safe(balance[0].get("TOTAL_PARENT_EQUITY"))
        cost = None
        if isinstance(profit, list) and profit:
            cost = _safe(profit[0].get("TOTAL_OPERATE_COST"))

        result["key_indicators"] = {
            "roe": _fmt_pct(
                round(net_profit / parent_equity * 100, 2)
                if net_profit and parent_equity else None
            ),
            "roa": _fmt_pct(
                round(net_profit / total_assets * 100, 2)
                if net_profit and total_assets else None
            ),
            "gross_margin": _fmt_pct(
                round((1 - cost / revenue) * 100, 2) if revenue and cost else None
            ),
            "net_margin": _fmt_pct(
                round(net_profit / revenue * 100, 2) if net_profit and revenue else None
            ),
            "debt_to_asset": _fmt_pct(
                round(m.get("资产负债率", 0) * 100, 2) if m.get("资产负债率") else None
            ),
        }

    return result


def register_composite_tools():
    """注册组合技能：analyze_stock、sector_analysis、compare_stocks、analyze_financials。"""
    registry.register_tool(Tool(
        name="analyze_stock",
        description="一键获取个股全维度分析数据，包括基本信息、详细估值、技术指标、新闻和情绪。当用户要求'分析某只股票''深度分析''全面评估'时调用，比分别调用多个工具更高效。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 600519"},
            },
            "required": ["code"],
        },
        executor=_analyze_stock,
    ))

    registry.register_tool(Tool(
        name="analyze_financials",
        description="一键获取个股完整财报数据，包括资产负债表、利润表、现金流量表（最近4期）、关键财务指标汇总和原始财务数据。当用户要求'分析财报''财务分析''看下财报''利润表''资产负债表''现金流量表'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 600519"},
            },
            "required": ["code"],
        },
        executor=_analyze_financials,
    ))

    registry.register_tool(Tool(
        name="sector_analysis",
        description="行业综合分析，包括行业热度排名、行业内股票筛选和相关研报。当用户问'XX行业怎么样''分析XX行业'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "行业名称，如'白酒''半导体''新能源'"},
            },
            "required": ["name"],
        },
        executor=_sector_analysis,
    ))

    registry.register_tool(Tool(
        name="compare_stocks",
        description="多股对比分析，同时获取多只股票的基本信息和估值数据进行横向对比。最多支持5只股票。当用户问'XX和YY哪个好''对比几只股票'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "codes": {"type": "string", "description": "逗号分隔的股票代码，如'600519,000858'"},
            },
            "required": ["codes"],
        },
        executor=_compare_stocks,
    ))
