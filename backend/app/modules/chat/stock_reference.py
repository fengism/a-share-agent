"""Chat 层股票标的入口：合并 A 股与港股名称识别。"""

from __future__ import annotations

from app.financial_data.hk.name_reference import mentions_hk_stock_target
from app.financial_data.stock.profile.name_map import mentions_stock_target as mentions_a_share_stock_target
from app.financial_data.stock.profile.short_names import has_specific_stock_context

#: 能把「某只说不清的股票」变成代码的唯一工具。
RESOLVER_TOOL_NAME = "search_stocks"


def mentions_stock_target(message: str) -> bool:
    """消息是否指向 A 股或港股标的。"""
    return mentions_a_share_stock_target(message) or mentions_hk_stock_target(message)


def needs_stock_resolution(message: str) -> bool:
    """在谈论某只具体证券，却识别不出是哪一只（Layer C 消歧）。

    只看高精度的“具体标的”措辞：``has_stock_context`` 含“分析/怎么样”等泛化
    动词，用它会把“分析一下光伏行业估值”也误判成个股问题。
    """
    return has_specific_stock_context(message) and not mentions_stock_target(message)


__all__ = [
    "RESOLVER_TOOL_NAME",
    "has_specific_stock_context",
    "mentions_stock_target",
    "needs_stock_resolution",
]
