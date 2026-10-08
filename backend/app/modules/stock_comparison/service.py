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
            resolved_price = (
                info_data.get("current_price")
                if info_data.get("current_price") is not None
                else info_data.get("price")
            )
            result.update(
                {
                    "name": info_data.get("name") or code,
                    "price": resolved_price,
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

        # 港股额外从港股行情源补足涨跌幅、最新价与估值指标，并规范行业标识
        from app.core.market import is_hk_code
        if is_hk_code(code):
            from app.financial_data.hk.service import hk_market_service, normalize_hk_code
            try:
                norm_code = normalize_hk_code(code)
                quotes = await hk_market_service.get_stock_quotes(codes=[norm_code])
                quote = quotes.items[0] if quotes.items else None
                if quote:
                    if result.get("price") is None:
                        result["price"] = quote.price
                    if result.get("change_pct") is None:
                        result["change_pct"] = quote.change_pct
                    if result.get("pe_ttm") is None:
                        result["pe_ttm"] = quote.pe_ttm
                    if result.get("pb") is None:
                        result["pb"] = quote.pb
                    if result.get("market_cap") is None:
                        result["market_cap"] = quote.market_cap
            except Exception:
                pass
            if not result.get("industry"):
                result["industry"] = "港股上市公司"

        # 三路数据源各自可能失败。只在「该路确实失败」时把它负责的字段置 None，
        # 并补 *_error，让上游能区分「没有这个指标」和「这一路挂了」。
        # 判断一律用 `is None`：用真值判断会把合法的 0（pe_ttm=0 / pb=0）当成缺失。
        if isinstance(valuation, Exception):
            if result.get("pe_ttm") is None:
                result["pe_ttm"] = None
            if result.get("pb") is None:
                result["pb"] = None
            result["ps_ttm"] = None
            result["valuation_error"] = type(valuation).__name__
        else:
            if result.get("pe_ttm") is None:
                result["pe_ttm"] = valuation.pe_ttm
            if result.get("pb") is None:
                result["pb"] = valuation.pb
            result["ps_ttm"] = valuation.ps_ttm

        if isinstance(metrics, Exception):
            result.update({"revenue": None, "net_profit": None, "roe": None})
            if not is_hk_code(code):
                result["metrics_error"] = type(metrics).__name__
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
