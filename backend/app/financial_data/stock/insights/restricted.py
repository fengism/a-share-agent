"""个股限售股解禁日历与抛压监测服务。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import akshare_semaphore
from app.core.market import normalize_code
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _shanghai_today_str() -> str:
    """解禁日为北京时间自然日，"今日"边界必须按上海时区计算。

    此前用 UTC 日期：北京时间 0-8 点期间 UTC 日期仍是昨天，会把
    昨日已解禁的批次划入未来抛压统计。
    """
    return datetime.now(_SHANGHAI_TZ).strftime("%Y-%m-%d")


def _parse_float(val: Any) -> float | None:
    if val is None or val == "" or str(val).lower() == "nan":
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


async def get_restricted_shares_lift(code: str) -> dict[str, Any]:
    """获取指定个股未来及历史限售股解禁批次、解禁规模、股东数与流通盘抛压测算。"""
    normalized_code = normalize_code(code).raw
    cache_key = f"restricted_shares_lift_{normalized_code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today_str = _shanghai_today_str()

    upcoming_lifts: list[dict[str, Any]] = []
    past_lifts: list[dict[str, Any]] = []

    try:
        df = await provider_gateway.call_blocking(
            "akshare",
            "fetch_restricted_shares",
            get_provider("akshare").fetch_restricted_shares,
            normalized_code,
            semaphore=akshare_semaphore,
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                lift_date = str(row.get("解禁时间", "")).strip()[:10]
                if not lift_date or lift_date == "nan":
                    continue

                shares = _parse_float(row.get("实际解禁数量") or row.get("解禁数量"))
                market_val_wan = _parse_float(row.get("实际解禁数量市值"))
                ratio_total = _parse_float(row.get("占总市值比例"))
                ratio_float = _parse_float(row.get("占流通市值比例"))
                share_type = str(row.get("限售股类型", "")).strip()
                holders_count = int(row.get("解禁股东数") or 0) if str(row.get("解禁股东数", "")).isdigit() else None
                pre_price = _parse_float(row.get("解禁前一交易日收盘价"))
                pre_20d_pct = _parse_float(row.get("解禁前20日涨跌幅"))
                post_20d_pct = _parse_float(row.get("解禁后20日涨跌幅"))

                item = {
                    "lift_date": lift_date,
                    "share_type": share_type or "限售股份",
                    "shares_count": shares,
                    "market_value_wan": market_val_wan,
                    "ratio_in_total_shares_pct": ratio_total,
                    "ratio_in_float_shares_pct": ratio_float,
                    "holders_count": holders_count,
                    "pre_lift_price": pre_price,
                    "pre_20d_change_pct": pre_20d_pct,
                    "post_20d_change_pct": post_20d_pct,
                }

                if lift_date >= today_str:
                    upcoming_lifts.append(item)
                else:
                    past_lifts.append(item)
    except Exception as exc:
        logger.warning("获取 %s 限售解禁数据失败: %s", normalized_code, exc)

    # 排序：未来解禁按日期升序（最近的在前），历史解禁按日期降序
    upcoming_lifts.sort(key=lambda x: x["lift_date"])
    past_lifts.sort(key=lambda x: x["lift_date"], reverse=True)

    # 统计未来抛压
    total_upcoming_shares = sum(x["shares_count"] or 0 for x in upcoming_lifts)
    total_upcoming_ratio_float = sum(x["ratio_in_float_shares_pct"] or 0 for x in upcoming_lifts)

    next_lift = upcoming_lifts[0] if upcoming_lifts else None
    pressure_level = "无近期解禁风险"
    if next_lift:
        float_pct = next_lift.get("ratio_in_float_shares_pct") or 0
        if float_pct > 20:
            pressure_level = "极高抛压预警（单次解禁占流通盘超20%）"
        elif float_pct > 5:
            pressure_level = "中度抛压预警（单次解禁占流通盘5%~20%）"
        else:
            pressure_level = "轻度/正常解禁（占流通盘5%以内）"

    result = {
        "code": normalized_code,
        "query_date": today_str,
        "has_upcoming_lifts": bool(upcoming_lifts),
        "upcoming_lifts_count": len(upcoming_lifts),
        "next_lift_detail": next_lift,
        "pressure_risk_assessment": pressure_level,
        "total_upcoming_shares": total_upcoming_shares,
        "total_upcoming_ratio_float_pct": round(total_upcoming_ratio_float, 2),
        "upcoming_lifts": upcoming_lifts[:10],
        "recent_past_lifts": past_lifts[:5],
    }

    cache.set(cache_key, result, ttl=_CACHE_TTL_SECONDS)
    return result
