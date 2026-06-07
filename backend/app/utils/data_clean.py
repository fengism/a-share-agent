import pandas as pd


def rename_columns(df: pd.DataFrame, rename_map: dict[str, str]) -> pd.DataFrame:
    """Rename DataFrame columns according to the mapping.

    Param:
        df: source DataFrame
        rename_map: mapping of old column name to new column name
    Return:
        DataFrame with renamed columns
    """
    return df.rename(columns=rename_map)


def rename_and_keep_columns(df: pd.DataFrame, rename_map: dict[str, str]) -> pd.DataFrame:
    """Rename columns and keep only the columns listed in rename_map values.

    Param:
        df: source DataFrame
        rename_map: mapping of old column name to new column name
    Return:
        DataFrame with renamed columns, restricted to columns present after rename
    """
    result = df.rename(columns=rename_map)
    keep_cols = [column for column in rename_map.values() if column in result.columns]
    return result[keep_cols]


def coerce_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert specified columns to numeric, coercing invalid values to NaN.

    Param:
        df: source DataFrame
        columns: list of column names to convert to numeric
    Return:
        copy of the DataFrame with specified columns coerced to numeric
    """
    result = df.copy()
    for col in columns:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result


def safe_float(val, scale: float = 1) -> float | None:
    """Safely convert a value to float, optionally divided by scale.

    Param:
        val: value to convert
        scale: divisor applied to the result (default 1)
    Return:
        float value divided by scale, or None if conversion fails
    """
    if val is None or pd.isna(val) or val in ("N/A", "-", ""):
        return None
    try:
        return float(val) / scale
    except (ValueError, TypeError):
        return None


def safe_int(val) -> int | None:
    """Safely convert a value to int via float round-trip.

    Param:
        val: value to convert
    Return:
        int value, or None if conversion fails
    """
    if val is None or pd.isna(val) or val in ("N/A", "-", ""):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_string(val) -> str | None:
    """Safely convert a value to a stripped string.

    Param:
        val: value to convert
    Return:
        stripped string value, or None if empty or NaN
    """
    if val is None or pd.isna(val):
        return None
    text = str(val).strip()
    return text or None
