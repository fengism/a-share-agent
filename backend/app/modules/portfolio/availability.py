"""持仓可卖数量与最小交易单位。

A 股实行 T+1：当日买入的股份当日不可卖出；港股为 T+0，全部持仓可卖。
这里只做展示与提示，不阻断历史流水回放——历史数据可能来自券商导出或补录，
若在回放层强制 T+1 会让一笔已存在的同日买卖永久无法保存。
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date

from app.modules.portfolio.accounting import OpenLot, parse_trade_time
from app.modules.portfolio.schemas import is_hk_stock_code

A_SHARE_LOT_SIZE = 100
HK_LOT_SIZE = 1


def is_t_plus_one(stock_code: str) -> bool:
    """A 股为 T+1；港股按 T+0 处理。"""

    return not is_hk_stock_code(stock_code)


def lot_size(stock_code: str) -> int:
    """最小交易单位。

    港股每手股数因标的而异，行情接口未提供可靠的手数信息，按 1 股估算；
    A 股统一按 100 股一手。
    """

    return HK_LOT_SIZE if is_hk_stock_code(stock_code) else A_SHARE_LOT_SIZE


async def resolve_portfolio_as_of_date(stock_codes: Iterable[str] | None = None) -> date:
    """把“今天”对齐到最近一个已开盘的 A 股交易日。

    T+1 冻结必须按交易日而不是自然日判断：周五买入在周六、周日仍不可卖，
    节假日同理。纯港股组合按 T+0 处理，不需要交易日历，直接返回自然日。
    交易日历不可用时底层会自动降级为工作日近似。
    """

    from app.core.market import market_today
    from app.financial_data.market.trading_session import get_market_date_on_or_before

    codes = list(stock_codes or [])
    if not codes or not any(is_t_plus_one(code) for code in codes):
        return market_today()
    return await get_market_date_on_or_before(market_today())


def sellable_shares(open_lots: list[OpenLot], stock_code: str, *, as_of_date: date) -> int:
    """按 T+1 规则计算某只股票在指定日期开盘后的可卖股数。"""

    lots = [lot for lot in open_lots if lot.stock_code == stock_code]
    total = sum(lot.remaining_shares for lot in lots)
    if not is_t_plus_one(stock_code):
        return total
    return sum(lot.remaining_shares for lot in lots if parse_trade_time(lot.buy_time).date() < as_of_date)


def round_down_to_lot(shares: float, stock_code: str) -> int:
    """按最小交易单位向下取整（用于估算可买数量）。"""

    size = lot_size(stock_code)
    return int(shares / size) * size


def round_up_to_lot(shares: float, stock_code: str) -> int:
    """按最小交易单位向上取整（用于估算至少需要卖出的数量）。"""

    if shares <= 0:
        return 0
    size = lot_size(stock_code)
    return math.ceil(shares / size) * size


__all__ = [
    "A_SHARE_LOT_SIZE",
    "HK_LOT_SIZE",
    "is_t_plus_one",
    "lot_size",
    "resolve_portfolio_as_of_date",
    "round_down_to_lot",
    "round_up_to_lot",
    "sellable_shares",
]
