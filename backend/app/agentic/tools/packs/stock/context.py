from __future__ import annotations

import asyncio
import re
from collections.abc import Collection

from app.agentic.tools.packs.stock import helpers as stock_helpers
from app.core.market import is_hk_code

_STOCK_NAME_SUFFIX_PATTERN = re.compile(r"(股份|集团|科技|控股|实业|发展|国际|A|B)$")


def name_in_message(name: str, message: str) -> bool:
    normalized_name = (name or "").strip()
    if not normalized_name:
        return False
    if normalized_name in message:
        return True
    core_name = _STOCK_NAME_SUFFIX_PATTERN.sub("", normalized_name)
    return len(core_name) >= 2 and core_name in message


async def resolve_stock_context(
    message: str,
    stock_codes: Collection[str] = (),
) -> str:
    codes = list(dict.fromkeys(stock_codes))
    if codes:
        stocks = [{"code": code, "name": ""} for code in codes][:3]
    else:
        search_result = await stock_helpers.search_stocks(query=message)
        if isinstance(search_result, dict) and search_result.get("error"):
            return ""
        if not search_result:
            return ""
        candidates = search_result if isinstance(search_result, list) else [search_result]
        stocks = [
            stock
            for stock in candidates
            if name_in_message(stock.get("name", ""), message)
        ][:3]
        if not stocks:
            return ""

    resolved = await asyncio.gather(*(_resolve_stock(stock) for stock in stocks))
    lines = ["[股票信息预解析 — 已获取代码和基本信息，后续分析直接使用，无需再次搜索]"]
    lines.extend(item for item in resolved if item)
    return "\n".join(lines) if len(lines) > 1 else ""


async def _resolve_stock(stock: dict) -> str:
    code = stock.get("code", stock.get("symbol", ""))
    name = stock.get("name", "")
    if not code:
        return ""

    if is_hk_code(code):
        hk_res = await stock_helpers.get_hk_stock_profile(code=code)
        if isinstance(hk_res, dict) and not hk_res.get("error"):
            quote = hk_res.get("quote", {})
            name = name or quote.get("name") or code
            price = quote.get("price")
            price_str = f"{price} HKD" if price is not None else "-"
            market_cap = quote.get("market_cap")
            cap_str = f"{market_cap}亿" if market_cap is not None else "-"
            pe = quote.get("pe_ttm")
            pe_str = f"{pe:.2f}" if isinstance(pe, (int, float)) else (str(pe) if pe else "-")
            return f"- [港股] {name}（{code}）：现价={price_str}，市值={cap_str}，PE={pe_str}"
        return f"- [港股] {name}（{code}）"

    info = await stock_helpers.get_stock_info(code=code)
    if isinstance(info, dict) and not info.get("error"):
        name = name or info.get("name", "")
        industry = info.get("industry", "")
        market_cap = info.get("market_cap", info.get("total_market_value", ""))
        pe = info.get("pe", info.get("pe_ttm", ""))
        return f"- {name}（{code}）：行业={industry}，市值={market_cap}，PE={pe}"
    return f"- {name}（{code}）"
