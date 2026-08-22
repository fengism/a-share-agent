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
