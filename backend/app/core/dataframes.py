import pandas as pd


def rename_columns(df: pd.DataFrame, rename_map: dict[str, str]) -> pd.DataFrame:
    """Rename DataFrame columns according to a mapping."""
    return df.rename(columns=rename_map)


def rename_and_keep_columns(
    df: pd.DataFrame,
    rename_map: dict[str, str],
) -> pd.DataFrame:
    """Rename columns and keep mapped output columns that exist."""
    result = df.rename(columns=rename_map)
    keep_columns = [column for column in rename_map.values() if column in result.columns]
    return result[keep_columns]


def coerce_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Coerce selected DataFrame columns to numeric values."""
    result = df.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def normalize_intraday_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize intraday columns to the aliases used downstream."""
    if df is None or df.empty:
        return pd.DataFrame()

    rename_map = {
        "时间": "time",
        "日期时间": "time",
        "date": "time",
        "时间戳": "time",
        "最新价": "price",
        "成交价": "price",
        "收盘": "price",
        "close": "price",
        "均价": "avg_price",
        "成交均价": "avg_price",
        "均均价": "avg_price",
        "成交量": "volume",
        "手数": "volume",
        "volume": "volume",
        "成交额": "amount",
        "amount": "amount",
        "涨跌幅": "change_pct",
    }
    result = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})
    if "time" not in result.columns or "price" not in result.columns:
        return pd.DataFrame()
    return result
