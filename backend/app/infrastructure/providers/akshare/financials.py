"""AkShare 财务与估值能力。"""

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.infrastructure.providers.akshare.loader import ak


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_stock_financials(symbol: str, indicator: str) -> pd.DataFrame:
    if indicator == "balance":
        return ak.stock_balance_sheet_by_report_em(symbol=symbol)
    if indicator == "profit":
        return ak.stock_profit_sheet_by_report_em(symbol=symbol)
    if indicator == "cashflow":
        return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
    raise ValueError(f"Unknown financial indicator: {indicator}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_stock_valuation_comparison(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_valuation_comparison_em(symbol=symbol)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def fetch_stock_valuation_baidu(
    symbol: str,
    indicator: str,
    period: str,
) -> pd.DataFrame:
    return ak.stock_zh_valuation_baidu(
        symbol=symbol,
        indicator=indicator,
        period=period,
    )
