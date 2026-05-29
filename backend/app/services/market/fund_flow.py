import logging
from datetime import datetime

import pandas as pd

from app.services.providers.ths import ths_provider as _ths_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _build_point(row) -> dict | None:
    time_value = row.get("time")
    if time_value is None or pd.isna(time_value):
        return None
    time_text = str(time_value).strip()
    if not time_text:
        return None
    hgt = safe_float(row.get("hgt_yi"))
    sgt = safe_float(row.get("sgt_yi"))
    total = hgt + sgt if hgt is not None and sgt is not None else None
    return {
        "time": time_text,
        "hgt": _round_or_none(hgt),
        "sgt": _round_or_none(sgt),
        "total": _round_or_none(total),
    }


async def get_hsgt_flow() -> dict:
    cache_key = dated_cache_key("hsgt_flow")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "unit": "亿元",
        "points": [],
    }

    try:
        df = await call_blocking(_ths_provider.fetch_hsgt_realtime)
    except Exception as exc:
        logger.warning(f"沪深股通分钟流向获取失败: error={exc}")
        raise

    if isinstance(df, pd.DataFrame) and not df.empty:
        for _, row in df.iterrows():
            point = _build_point(row)
            if point is not None:
                result["points"].append(point)

    cache.set(cache_key, result, ttl=60)
    return result
