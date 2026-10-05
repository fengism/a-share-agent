"""港股个股分析支撑：把行情快照映射成分析可用的结构。

港股没有 A 股口径的财务/估值/概念体系，因此这里只提供行情能证明的事实：
名称、现价、涨跌、成交与更新时间。缺失的字段一律不出现在返回结构里，由调用方
按数据缺口处理，绝不用其他市场的口径填补。
"""

from __future__ import annotations

from typing import Any

from app.financial_data.hk.service import hk_market_service, normalize_hk_code


async def get_hk_stock_profile(code: str) -> dict[str, Any]:
    """返回港股行情快照，作为港股分析的基础事实证据。"""
    normalized = normalize_hk_code(code)
    page = await hk_market_service.get_stock_quotes(codes=[normalized])
    for item in page.items:
        if item.code == normalized:
            return {"quote": item.model_dump(mode="json"), "source": page.source}
    raise LookupError(f"未获取到港股 {normalized} 的行情快照")


async def get_hk_market_overview() -> dict[str, Any]:
    """返回港股主要指数行情，作为港股分析的市场环境证据。"""
    indices = await hk_market_service.get_index_quotes()
    return {"indices": indices.model_dump(mode="json")}


__all__ = ["get_hk_market_overview", "get_hk_stock_profile"]