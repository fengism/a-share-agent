"""候选池筛选与行业统计。"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from app.modules.potential import constants
from app.modules.potential.common import _float_or_none, _normalize_code

_MAX_CANDIDATES = constants._MAX_CANDIDATES
_MIN_AMOUNT_YI = constants._MIN_AMOUNT_YI
_MIN_MARKET_CAP_YI = constants._MIN_MARKET_CAP_YI
_MAX_MARKET_CAP_YI = constants._MAX_MARKET_CAP_YI
_MIN_LISTING_DAYS = constants._MIN_LISTING_DAYS
_HEAD_CANDIDATE_LIMIT = constants._HEAD_CANDIDATE_LIMIT
_MID_CANDIDATE_LIMIT = constants._MID_CANDIDATE_LIMIT
_QUALITY_CANDIDATE_LIMIT = constants._QUALITY_CANDIDATE_LIMIT
_MID_MAX_AMOUNT_YI = constants._MID_MAX_AMOUNT_YI
_MID_MIN_TURNOVER_PCT = constants._MID_MIN_TURNOVER_PCT
_MID_MAX_TURNOVER_PCT = constants._MID_MAX_TURNOVER_PCT
_QUALITY_MIN_MARKET_CAP_YI = constants._QUALITY_MIN_MARKET_CAP_YI
_QUALITY_MAX_MARKET_CAP_YI = constants._QUALITY_MAX_MARKET_CAP_YI
_QUALITY_MAX_PE = constants._QUALITY_MAX_PE
_QUALITY_MAX_PB = constants._QUALITY_MAX_PB
_QUALITY_MIN_AMOUNT_YI = constants._QUALITY_MIN_AMOUNT_YI
_QUALITY_MAX_AMOUNT_YI = constants._QUALITY_MAX_AMOUNT_YI
_QUALITY_MIN_TURNOVER_PCT = constants._QUALITY_MIN_TURNOVER_PCT
_QUALITY_MAX_TURNOVER_PCT = constants._QUALITY_MAX_TURNOVER_PCT


def select_candidates(
    df: pd.DataFrame | None,
    master_records: list,
) -> list[dict]:
    """从全市场快照筛出风控合格的候选池。

    候选池分三层：高流动性龙头、中盘活跃股、估值/流动性合格的质量中盘。
    三层合并去重，兼顾趋势龙头、题材活跃股与基本面不过度离谱的中盘股。
    """
    if df is None or df.empty:
        return []
    frame = df.copy()
    frame["代码"] = frame["代码"].map(_normalize_code)
    frame = frame.drop_duplicates(subset=["代码"], keep="first")

    by_code = {record.code: record for record in master_records}
    frame["board"] = frame["代码"].map({code: record.board for code, record in by_code.items()})
    frame["industry"] = frame["代码"].map({code: record.industry for code, record in by_code.items()})
    frame["listing_date"] = frame["代码"].map({code: record.listing_date for code, record in by_code.items()})
    frame["amount_yi"] = pd.to_numeric(frame.get("成交额"), errors="coerce") / 1e8
    frame["turnover_pct"] = pd.to_numeric(frame.get("换手率"), errors="coerce")
    frame["price"] = pd.to_numeric(frame.get("最新价"), errors="coerce")
    frame["change_pct"] = pd.to_numeric(frame.get("涨跌幅"), errors="coerce")
    frame["market_cap_yi"] = pd.to_numeric(frame.get("总市值"), errors="coerce") / 1e8
    frame["float_market_cap_yi"] = pd.to_numeric(frame.get("流通市值"), errors="coerce") / 1e8
    frame["pe"] = pd.to_numeric(frame.get("市盈率-动态"), errors="coerce")
    frame["pb"] = pd.to_numeric(frame.get("市净率"), errors="coerce")

    name_text = frame["名称"].astype(str)
    mask = ~(name_text.str.upper().str.contains("ST", na=False) | name_text.str.contains("退", na=False))
    mask &= frame["amount_yi"].notna() & (frame["amount_yi"] >= _MIN_AMOUNT_YI)
    mask &= frame["price"].notna() & (frame["price"] > 1.0)
    mask &= (
        frame["market_cap_yi"].notna()
        & (frame["market_cap_yi"] >= _MIN_MARKET_CAP_YI)
        & (frame["market_cap_yi"] <= _MAX_MARKET_CAP_YI)
    )
    listing_days = (pd.Timestamp.now() - pd.to_datetime(frame["listing_date"], errors="coerce")).dt.days
    mask &= listing_days.isna() | (listing_days >= _MIN_LISTING_DAYS)
    frame = frame[mask]

    # 1. 头部高流动性龙头：成交额前 _HEAD_CANDIDATE_LIMIT 名
    head_candidates = frame.sort_values(by="amount_yi", ascending=False).head(_HEAD_CANDIDATE_LIMIT)
    # 2. 中盘活跃股：成交额适中且换手率在活跃区间
    mid_pool = frame[
        (frame["amount_yi"] <= _MID_MAX_AMOUNT_YI)
        & (frame["turnover_pct"] >= _MID_MIN_TURNOVER_PCT)
        & (frame["turnover_pct"] <= _MID_MAX_TURNOVER_PCT)
    ]
    mid_candidates = mid_pool.sort_values(by="turnover_pct", ascending=False).head(_MID_CANDIDATE_LIMIT)
    # 3. 质量中盘：市值/估值/流动性适中，按成交额取前 N 名
    quality_pool = frame[
        (frame["market_cap_yi"] >= _QUALITY_MIN_MARKET_CAP_YI)
        & (frame["market_cap_yi"] <= _QUALITY_MAX_MARKET_CAP_YI)
        & (frame["pe"] > 0)
        & (frame["pe"] <= _QUALITY_MAX_PE)
        & (frame["pb"] > 0)
        & (frame["pb"] <= _QUALITY_MAX_PB)
        & (frame["amount_yi"] >= _QUALITY_MIN_AMOUNT_YI)
        & (frame["amount_yi"] <= _QUALITY_MAX_AMOUNT_YI)
        & (frame["turnover_pct"] >= _QUALITY_MIN_TURNOVER_PCT)
        & (frame["turnover_pct"] <= _QUALITY_MAX_TURNOVER_PCT)
    ]
    quality_candidates = quality_pool.sort_values(by="amount_yi", ascending=False).head(_QUALITY_CANDIDATE_LIMIT)

    merged_frame = pd.concat([head_candidates, mid_candidates, quality_candidates]).drop_duplicates(
        subset=["代码"], keep="first"
    )
    selected = merged_frame.head(_MAX_CANDIDATES)

    return [
        {
            "code": str(row["代码"]),
            "name": str(row["名称"]),
            "price": _float_or_none(row.get("最新价")),
            "change_pct": _float_or_none(row.get("涨跌幅")),
            "market_cap": _float_or_none(row.get("总市值")) / 1e8 if _float_or_none(row.get("总市值")) else None,
            "float_market_cap": (
                _float_or_none(row.get("流通市值")) / 1e8 if _float_or_none(row.get("流通市值")) else None
            ),
            "turnover_pct": _float_or_none(row.get("换手率")),
            "amount": _float_or_none(row.get("amount_yi")),
            "industry": row.get("industry") if isinstance(row.get("industry"), str) else None,
            "board": row.get("board") if isinstance(row.get("board"), str) else None,
            "pe": _float_or_none(row.get("pe")),
            "pb": _float_or_none(row.get("pb")),
            "open": _float_or_none(row.get("今开")),
            "high": _float_or_none(row.get("最高")),
            "low": _float_or_none(row.get("最低")),
            "prev_close": _float_or_none(row.get("昨收")),
            "volume": _float_or_none(row.get("成交量")),
        }
        for _, row in selected.iterrows()
    ]

def _industry_stats(df: pd.DataFrame | None, master_records: list) -> dict[str, dict]:
    """按行业统计当日中位涨幅与成交额占比，用于行业强弱打分。"""
    if df is None or df.empty or not master_records:
        return {}
    industry_by_code = {record.code: record.industry for record in master_records if record.industry}
    if not industry_by_code:
        return {}
    frame = pd.DataFrame(
        {
            "code": df.get("代码", pd.Series(dtype=object)).map(_normalize_code),
            "change_pct": pd.to_numeric(df.get("涨跌幅"), errors="coerce"),
            "amount_yi": pd.to_numeric(df.get("成交额"), errors="coerce") / 1e8,
        }
    )
    frame["industry"] = frame["code"].map(industry_by_code)
    frame = frame.dropna(subset=["industry", "change_pct", "amount_yi"])
    if frame.empty:
        return {}
    total_amount = float(frame["amount_yi"].sum())
    stats: dict[str, dict] = {}
    for industry, group in frame.groupby("industry"):
        if len(group) < 2:
            continue
        median_change = float(group["change_pct"].median())
        amount = float(group["amount_yi"].sum())
        stats[str(industry)] = {
            "median_change_pct": round(median_change, 2) if math.isfinite(median_change) else 0.0,
            "amount_share": round(amount / total_amount, 4) if total_amount > 0 else 0.0,
            "count": int(len(group)),
        }
    return stats

def _spot_as_of_date(df: pd.DataFrame | None) -> date | None:
    """读取全市场快照的生成日期。

    仅用于日志与诊断：快照生成时间可能晚于行情所属交易日（例如周末
    重新抓取到周五收盘数据），因此不能直接拿它做前视偏差判断。
    """
    if df is None:
        return None
    value = df.attrs.get("stock_spot_as_of")
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
