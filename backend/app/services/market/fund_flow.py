import logging
from datetime import datetime

import pandas as pd

from app.services.providers.ths import ths_provider as _ths_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


def _round_or_none(value: float | None) -> float | None:
    """对浮点数保留 4 位小数，None 透传。

    Param:
        value: 待处理的浮点数或 None
    Return:
        四舍五入后的数值或 None
    """
    if value is None:
        return None
    return round(value, 4)


def _build_point(row) -> dict | None:
    """从 DataFrame 行构造单个北向分钟流向点。

    Param:
        row: pandas 行对象，包含 time/hgt_yi/sgt_yi 字段
    Return:
        包含 time/hgt/sgt/total 的字典，时间字段缺失时返回 None
    """
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
    """获取沪深股通分钟级资金流向，并持久化每日 15:00 收盘数据。

    Param:
        无
    Return:
        包含 updated_at/unit/points 的字典，points 为分钟级流向点列表
    """
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

    # 持久化到 SQLite（仅保存收盘 15:00 数据）
    try:
        from app.db.hsgt_store import save_hsgt_flow
        close_points = [p for p in result["points"] if p["time"].endswith("15:00")]
        if close_points:
            save_hsgt_flow(close_points[0]["time"][:10], close_points, result["updated_at"])
    except Exception as exc:
        logger.warning(f"北向数据持久化失败: {exc}")

    return result
