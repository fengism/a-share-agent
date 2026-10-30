import asyncio
import logging

import pandas as pd

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.market import safe_float, safe_string
from app.domain.stock import StockConcept
from app.financial_data.stock.public import (
    ExchangeStockMaster,
    get_exchange_stock_master,
    get_spot_snapshot,
)
from app.modules.screener.schemas import ScreenerFilter, ScreenerItem, ScreenerResult

logger = logging.getLogger(__name__)


def _normalize_candidate_code(value: object) -> str:
    text = str(value or "").strip()
    if text[:2].upper() in {"SH", "SZ", "BJ"}:
        text = text[2:]
    return text.zfill(6) if text.isdigit() else text


async def _get_exchange_master_optional() -> ExchangeStockMaster | None:
    try:
        return await asyncio.wait_for(get_exchange_stock_master(), timeout=2.0)
    except Exception as exc:
        logger.warning("交易所股票主档获取失败，筛选将跳过交易所元数据: %s", exc)
        return None


def _infer_board_by_code(code: str) -> str:
    if code.startswith(("688", "689")):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("4", "8", "920")):
        return "北交所"
    return "主板"


def _merge_exchange_master(df: pd.DataFrame, master: ExchangeStockMaster | None) -> pd.DataFrame:
    result = df.copy()
    result["代码"] = result["代码"].map(_normalize_candidate_code)
    result = result.drop_duplicates(subset=["代码"], keep="first")
    if master is None or not master.records:
        result["exchange_industry"] = None
        result["exchange"] = None
        result["board"] = result["代码"].map(_infer_board_by_code)
        result["listing_date"] = None
        return result

    by_code = {record.code: record for record in master.records}
    if master.complete:
        result = result[result["代码"].isin(by_code)].copy()
    official_names = result["代码"].map({code: record.name for code, record in by_code.items()})
    result["名称"] = official_names.fillna(result["名称"])
    result["exchange_industry"] = result["代码"].map({code: record.industry for code, record in by_code.items()})
    result["exchange"] = result["代码"].map({code: record.exchange for code, record in by_code.items()})
    result["board"] = result["代码"].map({code: record.board for code, record in by_code.items()})
    result["board"] = result["board"].fillna(result["代码"].map(_infer_board_by_code))
    result["listing_date"] = result["代码"].map({code: record.listing_date for code, record in by_code.items()})
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


def _compute_composite_scores(df: pd.DataFrame) -> pd.Series:
    """计算多因子综合得分 (0~100): 40% 估值安全度 + 40% 动量活跃度 + 20% 流动性稳定性。"""
    n = len(df)
    if n == 0:
        return pd.Series(dtype=float, index=df.index)
    if n == 1:
        return pd.Series([75.0], index=df.index)

    # 1. 估值得分 (越低越好，<=0 视为亏损/异常打底分)
    pe = pd.to_numeric(df.get("pe_num"), errors="coerce")
    pb = pd.to_numeric(df.get("pb_num"), errors="coerce")
    valid_pe = pe.where(pe > 0)
    pe_rank = (1.0 - valid_pe.rank(pct=True, ascending=True)).fillna(0.2) * 100
    valid_pb = pb.where(pb > 0)
    pb_rank = (1.0 - valid_pb.rank(pct=True, ascending=True)).fillna(0.2) * 100
    value_score = 0.5 * pe_rank + 0.5 * pb_rank

    # 2. 动量得分 (60日涨幅 + 日内涨跌幅 + 量比)
    chg_60d = pd.to_numeric(df.get("change_pct_60d_num"), errors="coerce")
    chg_daily = pd.to_numeric(df.get("change_pct_num"), errors="coerce")
    vol_ratio = pd.to_numeric(df.get("volume_ratio_num"), errors="coerce")
    m60_rank = chg_60d.rank(pct=True, ascending=True).fillna(0.5) * 100
    daily_rank = chg_daily.rank(pct=True, ascending=True).fillna(0.5) * 100
    vr_rank = vol_ratio.rank(pct=True, ascending=True).fillna(0.5) * 100
    momentum_score = 0.4 * m60_rank + 0.3 * daily_rank + 0.3 * vr_rank

    # 3. 流动性与市值规模得分 (中大市值与适度换手)
    cap = pd.to_numeric(df.get("market_cap_yi"), errors="coerce")
    turnover = pd.to_numeric(df.get("turnover_pct_num"), errors="coerce")
    cap_rank = cap.rank(pct=True, ascending=True).fillna(0.5) * 100
    to_dist = (turnover - 6.0).abs()
    to_rank = (1.0 - to_dist.rank(pct=True, ascending=True)).fillna(0.5) * 100
    quality_score = 0.5 * cap_rank + 0.5 * to_rank

    raw_composite = 0.4 * value_score + 0.4 * momentum_score + 0.2 * quality_score
    return raw_composite.round(1)


def _screen_dataframe(
    df: pd.DataFrame,
    second_industry_map: dict[str, str] | dict[str, dict[str, str]],
    exchange_master: ExchangeStockMaster | None,
    filters: ScreenerFilter,
    concept_map: dict[str, list[str]] | None = None,
) -> ScreenerResult:
    """对全市场快照执行过滤、排序与分页（CPU 密集同步函数，必须经 call_blocking 调度到线程池）。

    注意：入参 df 可能是共享缓存对象，本函数只读它，所有写入都发生在 _merge_exchange_master 的副本上。
    """
    df = _merge_exchange_master(df, exchange_master)

    def _extract_ind(code: object, key: str) -> str | None:
        val = second_industry_map.get(str(code))
        if isinstance(val, dict):
            return safe_string(val.get(key))
        if key == "level2":
            return safe_string(val)
        return None

    def _extract_code(code: object) -> str:
        val = second_industry_map.get(str(code))
        if isinstance(val, dict):
            return safe_string(val.get("code")) or ""
        return ""

    df["first_industry"] = df["代码"].map(lambda code: _extract_ind(code, "level1"))
    df["second_industry"] = df["代码"].map(lambda code: _extract_ind(code, "level2"))
    df["third_industry"] = df["代码"].map(lambda code: _extract_ind(code, "level3"))
    df["third_industry_code"] = df["代码"].map(_extract_code)
    df["concepts"] = df["代码"].map(lambda code: (concept_map or {}).get(str(code), []))

    candidate_count = len(df)
    has_sw_ind = df["first_industry"].notna() | df["second_industry"].notna() | df["third_industry"].notna()
    sw_industry_coverage = float(has_sw_ind.sum()) / candidate_count if candidate_count else 0.0
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
        "量比": "volume_ratio_num",
        "60日涨跌幅": "change_pct_60d_num",
    }
    for source_col, numeric_col in numeric_col_map.items():
        if source_col in df.columns:
            df[numeric_col] = pd.to_numeric(df[source_col], errors="coerce")
        else:
            df[numeric_col] = None

    df["market_cap_yi"] = df["market_cap_raw_num"] / 1e8

    # 计算日内振幅 (%)
    if "最高" in df.columns and "最低" in df.columns:
        high = pd.to_numeric(df["最高"], errors="coerce")
        low = pd.to_numeric(df["最低"], errors="coerce")
        prev_close = pd.to_numeric(df.get("昨收"), errors="coerce") if "昨收" in df.columns else pd.Series(dtype=float, index=df.index)
        open_price = pd.to_numeric(df.get("今开"), errors="coerce") if "今开" in df.columns else pd.Series(dtype=float, index=df.index)
        valid_prev = prev_close.where(prev_close > 0).fillna(open_price.where(open_price > 0))
        df["amplitude_num"] = ((high - low) / valid_prev) * 100
    else:
        df["amplitude_num"] = None

    mask = pd.Series([True] * len(df), index=df.index)
    if filters.pe_min is not None:
        mask &= df["pe_num"] >= filters.pe_min
    if filters.pe_max is not None:
        mask &= df["pe_num"] <= filters.pe_max
    if filters.pb_min is not None:
        mask &= df["pb_num"] >= filters.pb_min
    if filters.pb_max is not None:
        mask &= df["pb_num"] <= filters.pb_max
    # 破净股筛选: PB > 0 且 PB <= 1.0
    if filters.is_broken_net:
        mask &= df["pb_num"].notna() & (df["pb_num"] > 0) & (df["pb_num"] <= 1.0)
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
    if filters.amplitude_min is not None:
        mask &= df["amplitude_num"].notna() & (df["amplitude_num"] >= filters.amplitude_min)
    if filters.amplitude_max is not None:
        mask &= df["amplitude_num"].notna() & (df["amplitude_num"] <= filters.amplitude_max)
    if filters.volume_ratio_min is not None:
        mask &= df["volume_ratio_num"].notna() & (df["volume_ratio_num"] >= filters.volume_ratio_min)
    if filters.volume_ratio_max is not None:
        mask &= df["volume_ratio_num"].notna() & (df["volume_ratio_num"] <= filters.volume_ratio_max)
    if filters.change_pct_60d_min is not None:
        mask &= df["change_pct_60d_num"].notna() & (df["change_pct_60d_num"] >= filters.change_pct_60d_min)
    if filters.change_pct_60d_max is not None:
        mask &= df["change_pct_60d_num"].notna() & (df["change_pct_60d_num"] <= filters.change_pct_60d_max)
    if filters.industries:
        target_industries = set(filters.industries)
        industry_match = (
            df["first_industry"].isin(target_industries)
            | df["second_industry"].isin(target_industries)
            | df["third_industry"].isin(target_industries)
        )
        mask &= industry_match
    if filters.concepts:
        target_concepts = set(filters.concepts)
        concept_match = df["concepts"].map(lambda c_list: bool(target_concepts.intersection(c_list or [])))
        mask &= concept_match
    # 市场板块筛选（board 来自交易所 master；master 缺失时不生效，避免误杀全市场）
    if filters.markets and df["board"].notna().any():
        mask &= df["board"].isin(filters.markets)

    # ── 风控过滤（参考多 Agent 决策链路的强制风控 gate）──
    name_text = df["名称"].astype(str)
    st_mask = name_text.str.upper().str.contains("ST", na=False) | name_text.str.contains("退", na=False)
    risk_excluded_st = int((mask & st_mask).sum())
    if filters.exclude_st:
        mask &= ~st_mask

    listing_mask = pd.Series(False, index=df.index)
    if filters.min_listing_days is not None and filters.min_listing_days > 0:
        listing_dates = pd.to_datetime(df["listing_date"], errors="coerce")
        listing_days = (pd.Timestamp.now() - listing_dates).dt.days
        # 上市日期缺失时不过滤，避免数据源缺元数据时误杀全市场
        listing_mask = mask & (listing_days.notna() & (listing_days < filters.min_listing_days))
        risk_excluded_new_listing = int(listing_mask.sum())
        mask &= ~listing_mask
    else:
        risk_excluded_new_listing = 0

    amount_mask = pd.Series(False, index=df.index)
    if filters.min_amount_yi is not None and filters.min_amount_yi > 0:
        if "成交额" in df.columns:
            amount_yi = pd.to_numeric(df["成交额"], errors="coerce") / 1e8
            amount_mask = mask & (amount_yi.notna() & (amount_yi < filters.min_amount_yi))
            risk_excluded_low_liquidity = int(amount_mask.sum())
            mask &= ~amount_mask
    else:
        risk_excluded_low_liquidity = 0

    filtered = df[mask].copy()
    filtered["second_industry"] = filtered["second_industry"].map(safe_string)
    filtered["composite_score_num"] = _compute_composite_scores(filtered)

    sort_col_map = {
        "market_cap": "market_cap_yi",
        "pe": "pe_num",
        "pb": "pb_num",
        "price": "price_num",
        "change_pct": "change_pct_num",
        "turnover_pct": "turnover_pct_num",
        "volume": "volume_num",
        "amplitude": "amplitude_num",
        "volume_ratio": "volume_ratio_num",
        "change_pct_60d": "change_pct_60d_num",
        "composite_score": "composite_score_num",
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
        f_ind = safe_string(row.get("first_industry"))
        s_ind = safe_string(row.get("second_industry"))
        t_ind = safe_string(row.get("third_industry"))
        t_code = safe_string(row.get("third_industry_code")) or ""
        raw_concepts = row.get("concepts")
        stock_concepts = list(raw_concepts) if isinstance(raw_concepts, list) else []

        pb_val = safe_float(row.get("市净率"))
        is_broken = pb_val is not None and 0 < pb_val <= 1.0
        amp_raw = safe_float(row.get("amplitude_num"))
        amp_val = round(amp_raw, 2) if amp_raw is not None else None
        vol_ratio_raw = safe_float(row.get("volume_ratio_num"))
        vol_ratio_val = round(vol_ratio_raw, 2) if vol_ratio_raw is not None else None
        chg_60d_raw = safe_float(row.get("change_pct_60d_num"))
        chg_60d_val = round(chg_60d_raw, 2) if chg_60d_raw is not None else None
        comp_score_raw = safe_float(row.get("composite_score_num"))
        comp_score_val = round(comp_score_raw, 1) if comp_score_raw is not None else None

        items.append(
            ScreenerItem(
                code=str(row["代码"]),
                name=str(row["名称"]),
                price=safe_float(row.get("最新价")),
                change_pct=safe_float(row.get("涨跌幅")),
                pe_ttm=safe_float(row.get("市盈率-动态")),
                pb=pb_val,
                market_cap=safe_float(row.get("market_cap_yi")),
                turnover_pct=safe_float(row.get("换手率")),
                volume=safe_float(row.get("成交量")),
                amplitude=amp_val,
                volume_ratio=vol_ratio_val,
                change_pct_60d=chg_60d_val,
                composite_score=comp_score_val,
                is_broken_net=is_broken,
                exchange=safe_string(row.get("exchange")),
                board=safe_string(row.get("board")),
                listing_date=safe_string(row.get("listing_date")),
                exchange_industry=safe_string(row.get("exchange_industry")),
                first_industry=_build_industry_concept(f_ind),
                second_industry=_build_industry_concept(s_ind),
                third_industry=StockConcept(code=t_code, name=t_ind) if t_ind else None,
                concepts=stock_concepts,
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
        risk_excluded_st=risk_excluded_st,
        risk_excluded_new_listing=risk_excluded_new_listing,
        risk_excluded_low_liquidity=risk_excluded_low_liquidity,
    )


async def screen_stocks(filters: ScreenerFilter) -> ScreenerResult:
    """按筛选条件过滤股票全市场快照并返回分页结果。

    Param:
        filters: ScreenerFilter 过滤条件对象
    Return:
        ScreenerResult 包含分页后的股票条目与总数
    """
    from app.modules.industry_classification.public import a_share_all_levels_mapping
    from app.modules.stock_concept.public import a_share_all_concepts_mapping

    df, industry_levels_map, concept_map, exchange_master = await asyncio.gather(
        get_spot_snapshot(),
        call_blocking(a_share_all_levels_mapping, semaphore=misc_semaphore),
        call_blocking(a_share_all_concepts_mapping, semaphore=misc_semaphore),
        _get_exchange_master_optional(),
    )
    if df is None:
        raise ValueError("无法获取市场数据")

    # 全市场 5000+ 行的 pandas 过滤/排序是 CPU 密集同步操作，
    # 必须调度到线程池执行，避免阻塞事件循环上的其他请求。
    return await call_blocking(
        _screen_dataframe,
        df,
        industry_levels_map,
        exchange_master,
        filters,
        concept_map=concept_map,
        semaphore=misc_semaphore,
    )
