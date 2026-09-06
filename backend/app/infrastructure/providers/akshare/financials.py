"""AkShare 财务与估值能力。"""

import pandas as pd

from app.infrastructure.providers.akshare.loader import ak


def fetch_stock_financials(symbol: str, indicator: str) -> pd.DataFrame:
    if indicator == "balance":
        return ak.stock_balance_sheet_by_report_em(symbol=symbol)
    if indicator == "profit":
        return ak.stock_profit_sheet_by_report_em(symbol=symbol)
    if indicator == "cashflow":
        return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
    raise ValueError(f"Unknown financial indicator: {indicator}")


def fetch_stock_valuation_comparison(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_valuation_comparison_em(symbol=symbol)


VALID_BAIDU_VALUATION_INDICATORS = {
    "总市值",
    "市盈率(TTM)",
    "市盈率(静)",
    "市净率",
    "市现率",
}


def fetch_stock_valuation_baidu(
    symbol: str,
    indicator: str,
    period: str,
) -> pd.DataFrame:
    if indicator not in VALID_BAIDU_VALUATION_INDICATORS:
        return pd.DataFrame()
    try:
        df = ak.stock_zh_valuation_baidu(
            symbol=symbol,
            indicator=indicator,
            period=period,
        )
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame()
        return df
    except (KeyError, TypeError, IndexError, ValueError, AttributeError):
        return pd.DataFrame()
