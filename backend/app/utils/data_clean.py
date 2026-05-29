import pandas as pd


def rename_columns(df: pd.DataFrame, rename_map: dict[str, str]) -> pd.DataFrame:
    return df.rename(columns=rename_map)


def rename_and_keep_columns(df: pd.DataFrame, rename_map: dict[str, str]) -> pd.DataFrame:
    result = df.rename(columns=rename_map)
    keep_cols = [column for column in rename_map.values() if column in result.columns]
    return result[keep_cols]


def coerce_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result


def safe_float(val, scale: float = 1) -> float | None:
    if val is None or pd.isna(val) or val in ("N/A", "-", ""):
        return None
    try:
        return float(val) / scale
    except (ValueError, TypeError):
        return None


def safe_int(val) -> int | None:
    if val is None or pd.isna(val) or val in ("N/A", "-", ""):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_string(val) -> str | None:
    if val is None or pd.isna(val):
        return None
    text = str(val).strip()
    return text or None
