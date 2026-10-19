"""Chat 层股票标的入口：合并 A 股与港股名称识别。"""

from __future__ import annotations

from app.financial_data.hk.name_reference import mentions_hk_stock_target
from app.financial_data.stock.profile.name_map import mentions_stock_target as mentions_a_share_stock_target


def mentions_stock_target(message: str) -> bool:
    """消息是否指向 A 股或港股标的。"""
    return mentions_a_share_stock_target(message) or mentions_hk_stock_target(message)


__all__ = ["mentions_stock_target"]
