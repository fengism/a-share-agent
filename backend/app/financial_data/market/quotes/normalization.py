import pandas as pd

from app.constants.market import INDEX_FALLBACKS
from app.core.market import normalize_index_code, safe_float
from app.domain.market import IndexItem, MarketIndices


def normalize_indices(indices: list[IndexItem]) -> list[IndexItem]:
    """Filter and order index items to match the canonical INDEX_FALLBACKS order.

    Param:
        indices: list of IndexItem to normalize
    Return:
        filtered list of IndexItem, sorted by INDEX_FALLBACKS order
    """
    fallback_map = {code: (name, idx) for idx, (code, name, _secid) in enumerate(INDEX_FALLBACKS)}
    normalized: list[IndexItem] = []
    for item in indices:
        code = normalize_index_code(item.code)
        fallback = fallback_map.get(code)
        if fallback is None:
            continue
        fallback_name, _order = fallback
        normalized.append(
            IndexItem(
                code=code,
                name=item.name or fallback_name,
                price=item.price,
                change_pct=item.change_pct,
                volume=item.volume,
                amount=item.amount,
                open=item.open,
                high=item.high,
                low=item.low,
                amplitude=item.amplitude,
                pre_close=item.pre_close,
            )
        )

    normalized.sort(key=lambda item: fallback_map[item.code][1])
    return normalized


def build_indices_from_sina(df: pd.DataFrame) -> MarketIndices:
    """Build a MarketIndices object from a Sina quote DataFrame.

    Param:
        df: DataFrame with Sina-formatted index columns
    Return:
        MarketIndices containing normalized index items
    """
    indices: list[IndexItem] = []
    for _, row in df.iterrows():
        indices.append(
            IndexItem(
                code=normalize_index_code(str(row.get("代码", ""))),
                name=str(row.get("名称", "")),
                price=safe_float(row.get("最新价")),
                change_pct=safe_float(row.get("涨跌幅")),
                volume=safe_float(row.get("成交量"))/100,  # 新浪成交量单位为股，转换为手
                amount=safe_float(row.get("成交额")),
                open=safe_float(row.get("今开")),
                high=safe_float(row.get("最高")),
                low=safe_float(row.get("最低")),
                amplitude=safe_float(row.get("振幅")),
                pre_close=safe_float(row.get("昨收")),
            )
        )

    return MarketIndices(indices=normalize_indices(indices))


def filter_index_hist_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """Filter an index history DataFrame to the given date range.

    Param:
        df: DataFrame with a "date" column
        start_date: inclusive start date string (YYYY-MM-DD), or empty for no lower bound
        end_date: inclusive end date string (YYYY-MM-DD), or empty for no upper bound
    Return:
        filtered DataFrame with reset index and "date" column formatted as "YYYY-MM-DD"
    """
    if df.empty:
        return df
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date"])
    if start_date:
        result = result[result["date"] >= pd.to_datetime(start_date)]
    if end_date:
        result = result[result["date"] <= pd.to_datetime(end_date)]
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)
