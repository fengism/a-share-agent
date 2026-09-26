"""Shared acceptance checks for K-line Provider Chain responses."""

from datetime import date, timedelta

import pandas as pd

from app.core.market import market_today

_PERIOD_STALE_TOLERANCE_DAYS = {
    "daily": 20,
    "weekly": 45,
    "monthly": 70,
}


def _column(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return frame[name]
    return pd.Series(index=frame.index, dtype="object")


def validate_kline_frame(
    source: str,
    frame: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    period: str,
    today: date | None = None,
) -> pd.DataFrame:
    """Filter malformed rows and reject empty, out-of-range, or clearly stale data."""
    if frame.empty:
        raise ValueError(f"{source} 未返回有效 K 线")
    parsed_dates = pd.to_datetime(_column(frame, "日期", "date"), errors="coerce")
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError(f"{source} K 线请求日期无效")

    open_price = pd.to_numeric(_column(frame, "开盘", "open"), errors="coerce")
    close_price = pd.to_numeric(_column(frame, "收盘", "close"), errors="coerce")
    high_price = pd.to_numeric(_column(frame, "最高", "high"), errors="coerce")
    low_price = pd.to_numeric(_column(frame, "最低", "low"), errors="coerce")
    valid = (
        parsed_dates.notna()
        & (parsed_dates >= start)
        & (parsed_dates <= end)
        & (open_price > 0)
        & (close_price > 0)
        & (high_price >= pd.concat([open_price, close_price], axis=1).max(axis=1))
        & (low_price > 0)
        & (low_price <= pd.concat([open_price, close_price], axis=1).min(axis=1))
    )
    accepted = frame.loc[valid].copy()
    accepted_dates = parsed_dates.loc[valid]
    if accepted.empty:
        raise ValueError(f"{source} K 线 OHLC 或日期范围无有效数据")

    expected_end = min(end.date(), today or market_today())
    tolerance = _PERIOD_STALE_TOLERANCE_DAYS.get(period, 20)
    latest_date = accepted_dates.max().date()
    if latest_date < expected_end - timedelta(days=tolerance):
        raise ValueError(
            f"{source} K 线数据陈旧: latest={latest_date.isoformat()} expected_end={expected_end.isoformat()}"
        )
    return accepted.reset_index(drop=True)
