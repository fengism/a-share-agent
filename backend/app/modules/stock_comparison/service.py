"""多股票指标对比服务。"""

import asyncio
from collections.abc import Sequence
from typing import Any, cast

from app.core.exceptions import InvalidRequestError
from app.financial_data.stock.public import (
    StockCompareItem,
    StockValuation,
    get_basic_info,
    get_financial_metrics,
    get_valuation,
)


def _normalize_codes(codes: Sequence[str] | str) -> list[str]:
    values = codes.split(",") if isinstance(codes, str) else codes
    code_list = [code.strip() for code in values if code.strip()]
    if len(code_list) > 5:
        raise InvalidRequestError("最多对比5只股票", code="stock.compare_too_many")
    if not code_list:
        raise InvalidRequestError("请输入至少一个股票代码", code="stock.compare_empty")
    return code_list


async def compare_stocks(codes: Sequence[str] | str) -> list[StockCompareItem]:
    """并发获取最多五只股票的资料、估值和财务指标。"""
    code_list = _normalize_codes(codes)

    async def fetch_one(code: str) -> StockCompareItem:
        responses = await asyncio.gather(
            get_basic_info(code),
            get_valuation(code),
            get_financial_metrics(code),
            return_exceptions=True,
        )
        info: Any = responses[0]
        valuation = cast(StockValuation | Exception, responses[1])
        metrics: Any = responses[2]

        result: dict[str, Any] = {"code": code}
        if isinstance(info, Exception):
            result["name"] = code
            result["info_error"] = str(info)
        else:
            info_data = info.model_dump()
            result.update(
                {
                    "name": info_data.get("name") or code,
                    "price": info_data.get("price"),
                    "change_pct": info_data.get("change_pct"),
                    "pe_ttm": info_data.get("pe_ttm"),
                    "pb": info_data.get("pb"),
                    "market_cap": info_data.get("market_cap"),
                    "turnover_pct": info_data.get("turnover_pct"),
                    "industry": (
                        info_data.get("first_industry", {}).get("name")
                        if info_data.get("first_industry")
                        else None
                    ),
                }
            )

        if isinstance(valuation, Exception):
            if not result.get("pe_ttm"):
                result["pe_ttm"] = None
            if not result.get("pb"):
                result["pb"] = None
            result["ps_ttm"] = None
        else:
            result["pe_ttm"] = result.get("pe_ttm") or valuation.pe_ttm
            result["pb"] = result.get("pb") or valuation.pb
            result["ps_ttm"] = valuation.ps_ttm

        if isinstance(metrics, Exception):
            result.update({"revenue": None, "net_profit": None, "roe": None})
        else:
            metric_values = metrics.metrics if metrics.metrics else {}
            result.update(
                {
                    "revenue": metric_values.get("营收"),
                    "net_profit": metric_values.get("净利润"),
                    "roe": metric_values.get("净资产收益率"),
                }
            )
        return StockCompareItem.model_validate(result)

    return list(await asyncio.gather(*(fetch_one(code) for code in code_list)))
