import logging
from datetime import datetime

import pandas as pd

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking, ths_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import safe_float
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)
_hsgt_flow_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()


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


async def _load_hsgt_flow() -> dict:
    result = {
        "updated_at": datetime.now(SHANGHAI_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
        "unit": "亿元",
        "points": [],
    }

    try:
        df = await provider_gateway.call(
            "ths",
            "hsgt_realtime",
            lambda: call_blocking(
                get_provider("ths").fetch_hsgt_realtime,
                semaphore=ths_semaphore,
            ),
        )
    except Exception as exc:
        logger.warning("沪深股通分钟流向获取失败: error=%s", exc)
        raise

    if isinstance(df, pd.DataFrame) and not df.empty:
        for _, row in df.iterrows():
            point = _build_point(row)
            if point is not None:
                result["points"].append(point)

    try:
        from app.infrastructure.persistence.hsgt_store import save_hsgt_flow

        close_points = [point for point in result["points"] if point["time"].endswith("15:00")]
        if close_points:
            save_hsgt_flow(close_points[0]["time"][:10], close_points, result["updated_at"])
    except Exception as exc:
        logger.warning("北向数据持久化失败: %s", exc)

    return result


async def get_hsgt_flow() -> dict:
    """获取沪深股通分钟级资金流向，并复用日 K 交易时段缓存策略。

    Param:
        无
    Return:
        包含 updated_at/unit/points 的字典，points 为分钟级流向点列表
    """
    now = datetime.now(SHANGHAI_TIMEZONE)
    policy = await resolve_market_data_cache_policy("daily", now.date(), now=now)
    cache_key = dated_cache_key("hsgt_flow")
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    async def load_and_cache() -> dict:
        result = await _load_hsgt_flow()
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _hsgt_flow_singleflight.do(cache_key, load_and_cache)


async def get_hsgt_flow_history(days: int = 30) -> list[dict]:
    """读取沪深股通历史分钟流向数据。

    Param:
        days: 查询天数，默认 30 天。
    Return:
        每天包含 date、updated_at 和 points 的字典列表。
    """
    from app.infrastructure.persistence.hsgt_store import query_hsgt_dates, query_hsgt_flow

    dates = query_hsgt_dates(limit=days)
    result = []
    for record in dates:
        date_str = record["date"]
        result.append(
            {
                "date": date_str,
                "updated_at": record.get("updated_at", ""),
                "points": query_hsgt_flow(date_str),
            }
        )
    return result
