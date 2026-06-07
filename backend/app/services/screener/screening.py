import pandas as pd

from app.models.screener import ScreenerFilter, ScreenerItem, ScreenerResult
from app.models.stock import StockConcept
from app.services.screener.industry import get_industry_mapping
from app.services.base.spot_snapshot import get_spot_snapshot
from app.utils.data_clean import safe_float, safe_string


def _build_industry_concept(name: str | None) -> StockConcept | None:
    """根据行业名称构造 StockConcept 对象。

    Param:
        name: 行业名称
    Return:
        StockConcept 对象，名称为空时返回 None
    """
    text = safe_string(name)
    if text is None:
        return None
    return StockConcept(code="", name=text)


async def screen_stocks(filters: ScreenerFilter) -> ScreenerResult:
    """按筛选条件过滤股票全市场快照并返回分页结果。

    Param:
        filters: ScreenerFilter 过滤条件对象
    Return:
        ScreenerResult 包含分页后的股票条目与总数
    """
    df = await get_spot_snapshot()
    if df is None:
        raise ValueError("无法获取市场数据")

    second_industry_map = await get_industry_mapping()
    df = df.copy()
    df["second_industry"] = df["代码"].map(lambda c: safe_string(second_industry_map.get(str(c))))

    numeric_col_map = {
        "最新价": "price_num",
        "涨跌幅": "change_pct_num",
        "换手率": "turnover_pct_num",
        "成交量": "volume_num",
        "市盈率-动态": "pe_num",
        "市净率": "pb_num",
        "总市值": "market_cap_raw_num",
    }
    for source_col, numeric_col in numeric_col_map.items():
        if source_col in df.columns:
            df[numeric_col] = pd.to_numeric(df[source_col], errors="coerce")
        else:
            df[numeric_col] = None

    df["market_cap_yi"] = df["market_cap_raw_num"] / 1e8

    mask = pd.Series([True] * len(df), index=df.index)
    if filters.pe_min is not None:
        mask &= df["pe_num"] >= filters.pe_min
    if filters.pe_max is not None:
        mask &= df["pe_num"] <= filters.pe_max
    if filters.pb_min is not None:
        mask &= df["pb_num"] >= filters.pb_min
    if filters.pb_max is not None:
        mask &= df["pb_num"] <= filters.pb_max
    if filters.price_min is not None:
        mask &= df["price_num"] >= filters.price_min
    if filters.price_max is not None:
        mask &= df["price_num"] <= filters.price_max
    if filters.market_cap_min is not None:
        mask &= df["market_cap_yi"] >= filters.market_cap_min
    if filters.market_cap_max is not None:
        mask &= df["market_cap_yi"] <= filters.market_cap_max
    if filters.change_pct_min is not None:
        mask &= df["change_pct_num"] >= filters.change_pct_min
    if filters.change_pct_max is not None:
        mask &= df["change_pct_num"] <= filters.change_pct_max
    if filters.turnover_pct_min is not None:
        mask &= df["turnover_pct_num"] >= filters.turnover_pct_min
    if filters.turnover_pct_max is not None:
        mask &= df["turnover_pct_num"] <= filters.turnover_pct_max
    if filters.industries:
        mask &= df["second_industry"].isin(filters.industries)

    filtered = df[mask].copy()
    filtered["second_industry"] = filtered["second_industry"].map(safe_string)

    sort_col_map = {
        "market_cap": "market_cap_yi",
        "pe": "pe_num",
        "pb": "pb_num",
        "price": "price_num",
        "change_pct": "change_pct_num",
        "turnover_pct": "turnover_pct_num",
        "volume": "volume_num",
    }
    sort_col = sort_col_map.get(filters.sort_by, "market_cap_yi")
    ascending = filters.sort_order == "asc"
    if sort_col in filtered.columns:
        filtered = filtered.sort_values(by=sort_col, ascending=ascending, na_position="last")

    total = len(filtered)
    start = (filters.page - 1) * filters.page_size
    end = start + filters.page_size
    page_data = filtered.iloc[start:end]

    items: list[ScreenerItem] = []
    for _, row in page_data.iterrows():
        items.append(
            ScreenerItem(
                code=str(row["代码"]),
                name=str(row["名称"]),
                price=safe_float(row.get("最新价")),
                change_pct=safe_float(row.get("涨跌幅")),
                pe_ttm=safe_float(row.get("市盈率-动态")),
                pb=safe_float(row.get("市净率")),
                market_cap=safe_float(row.get("market_cap_yi")),
                turnover_pct=safe_float(row.get("换手率")),
                volume=safe_float(row.get("成交量")),
                second_industry=_build_industry_concept(row.get("second_industry")),
            )
        )

    return ScreenerResult(items=items, total=total, page=filters.page, page_size=filters.page_size)
