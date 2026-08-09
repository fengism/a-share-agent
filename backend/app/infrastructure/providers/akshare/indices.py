"""AkShare 市场指数能力。"""

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.market import normalize_index_symbol
from app.infrastructure.providers.akshare.loader import ak


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_market_indices() -> pd.DataFrame:
    return ak.stock_zh_index_spot_em(symbol="沪深重要指数")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_market_indices_sina() -> pd.DataFrame:
    return ak.stock_zh_index_spot_sina()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_index_kline(
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    return ak.index_zh_a_hist(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_index_kline_sina(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_index_daily(symbol=normalize_index_symbol(symbol))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_index_kline_tencent(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_index_daily_tx(symbol=normalize_index_symbol(symbol))
