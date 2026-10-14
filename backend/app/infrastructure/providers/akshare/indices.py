"""AkShare 市场指数能力。"""

import pandas as pd

from app.core.market import normalize_index_symbol
from app.infrastructure.providers.akshare.loader import ak


def fetch_market_indices() -> pd.DataFrame:
    return ak.stock_zh_index_spot_em(symbol="沪深重要指数")


def fetch_market_indices_sina() -> pd.DataFrame:
    return ak.stock_zh_index_spot_sina()


def fetch_index_kline(
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    frame = ak.index_zh_a_hist(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    if not frame.empty and "成交量" in frame.columns:
        # AkShare 东方财富指数日线成交量单位为手；统一为股。与 stock.fetch_stock_kline
        # 对个股的处理保持一致——否则指数成交量会比腾讯/TDX/东财直连链小 100 倍。
        frame = frame.copy()
        frame["成交量"] = pd.to_numeric(frame["成交量"], errors="coerce") * 100
    return frame


def fetch_index_kline_sina(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_index_daily(symbol=normalize_index_symbol(symbol))


def fetch_index_kline_tencent(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_index_daily_tx(symbol=normalize_index_symbol(symbol))
