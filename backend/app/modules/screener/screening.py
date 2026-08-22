import asyncio

import pandas as pd

from app.core.market import safe_float, safe_string
from app.domain.stock import StockConcept
from app.financial_data.stock.public import (
    ExchangeStockMaster,
    get_exchange_stock_master,
    get_industry_mapping,
    get_spot_snapshot,
)
from app.modules.screener.schemas import ScreenerFilter, ScreenerItem, ScreenerResult


def _normalize_candidate_code(value: object) -> str:
    text = str(value or "").strip()
    if text[:2].upper() in {"SH", "SZ", "BJ"}:
        text = text[2:]
    return text.zfill(6) if text.isdigit() else text


async def _get_exchange_master_optional() -> ExchangeStockMaster | None:
    try:
        return await asyncio.wait_for(get_exchange_stock_master(), timeout=2.0)
    except Exception:
        return None


def _merge_exchange_master(df: pd.DataFrame, master: ExchangeStockMaster | None) -> pd.DataFrame:
    result = df.copy()
    result["代码"] = result["代码"].map(_normalize_candidate_code)
    result = result.drop_duplicates(subset=["代码"], keep="first")
    if master is None or not master.records:
        result["exchange_industry"] = None
        result["exchange"] = None
        result["board"] = None
        result["listing_date"] = None
        return result

    by_code = {record.code: record for record in master.records}
    if master.complete:
        result = result[result["代码"].isin(by_code)].copy()
    official_names = result["代码"].map({code: record.name for code, record in by_code.items()})
    result["名称"] = official_names.fillna(result["名称"])
    result["exchange_industry"] = result["代码"].map(
        {code: record.industry for code, record in by_code.items()}
    )
    result["exchange"] = result["代码"].map({code: record.exchange for code, record in by_code.items()})
    result["board"] = result["代码"].map({code: record.board for code, record in by_code.items()})
    result["listing_date"] = result["代码"].map(
        {code: record.listing_date for code, record in by_code.items()}
    )
    return result


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
    df, second_industry_map, exchange_master = await asyncio.gather(
        get_spot_snapshot(),
        get_industry_mapping(),
        _get_exchange_master_optional(),
    )
    if df is None:
        raise ValueError("无法获取市场数据")

    df = _merge_exchange_master(df, exchange_master)
    df["second_industry"] = df["代码"].map(
        lambda code: safe_string(second_industry_map.get(str(code)))
    )
    candidate_count = len(df)
    sw_industry_coverage = (
        float(df["second_industry"].notna().sum()) / candidate_count if candidate_count else 0.0
    )
    exchange_industry_coverage = (
        float(df["exchange_industry"].notna().sum()) / candidate_count if candidate_count else 0.0
    )

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
                exchange=safe_string(row.get("exchange")),
                board=safe_string(row.get("board")),
                listing_date=safe_string(row.get("listing_date")),
                exchange_industry=safe_string(row.get("exchange_industry")),
                second_industry=_build_industry_concept(row.get("second_industry")),
            )
        )

    return ScreenerResult(
        items=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        sw_industry_coverage=sw_industry_coverage,
        exchange_industry_coverage=exchange_industry_coverage,
        stock_master_complete=bool(exchange_master and exchange_master.complete),
    )
