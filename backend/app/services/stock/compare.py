"""多股对比分析服务。"""

import asyncio
import logging

from app.services.stock.basic_info import get_basic_info
from app.services.stock.valuation import get_valuation
from app.services.stock.financials import get_financial_metrics

logger = logging.getLogger(__name__)


async def compare_stocks(codes: str) -> list[dict]:
    """多股横向对比，获取每股的基本信息、估值数据、财务指标。

    Param:
        codes: 逗号分隔的股票代码，如 "600519,000858"，最多 5 个。
    Return:
        每只股票的合并数据列表。
    """
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) > 5:
        return [{"code": "_error", "name": "最多对比5只股票"}]
    if not code_list:
        return [{"code": "_error", "name": "请输入至少一个股票代码"}]

    async def fetch_one(code: str) -> dict:
        info_task = get_basic_info(code)
        val_task = get_valuation(code)
        metrics_task = get_financial_metrics(code)

        info, valuation, metrics = await asyncio.gather(
            info_task, val_task, metrics_task, return_exceptions=True,
        )

        result: dict = {"code": code}

        if isinstance(info, Exception):
            result["name"] = code
            result["info_error"] = str(info)
        else:
            d = info.model_dump()
            result["name"] = d.get("name", code)
            result["price"] = d.get("price")
            result["change_pct"] = d.get("change_pct")
            result["pe_ttm"] = d.get("pe_ttm")
            result["pb"] = d.get("pb")
            result["market_cap"] = d.get("market_cap")
            result["turnover_pct"] = d.get("turnover_pct")
            result["industry"] = d.get("first_industry", {}).get("name") if d.get("first_industry") else None

        if isinstance(valuation, Exception):
            if not result.get("pe_ttm"):
                result["pe_ttm"] = None
            if not result.get("pb"):
                result["pb"] = None
            result["ps_ttm"] = None
        else:
            result["pe_ttm"] = result.get("pe_ttm") or valuation.get("pe_ttm")
            result["pb"] = result.get("pb") or valuation.get("pb")
            result["ps_ttm"] = valuation.get("ps_ttm")

        if isinstance(metrics, Exception):
            result["revenue"] = None
            result["net_profit"] = None
            result["roe"] = None
        else:
            m = metrics.metrics if metrics.metrics else {}
            result["revenue"] = m.get("营业收入")
            result["net_profit"] = m.get("净利润")
            result["roe"] = m.get("净资产收益率")

        return result

    results = await asyncio.gather(*[fetch_one(c) for c in code_list])
    return list(results)
