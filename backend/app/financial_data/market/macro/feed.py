"""资讯页「宏观数据」聚合：国家统计局最新发布 + 央行新闻/政策解读 + 利率。"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, timedelta
from typing import Any

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import nbs_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import market_today
from app.domain.timezones import market_now
from app.financial_data.market.macro.schemas import (
    MacroFeedItem,
    MacroFeedResponse,
    MacroRateItem,
)
from app.financial_data.market.macro.service import _load_macro_metric
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

MACRO_FEED_CACHE_TTL_SECONDS = 15 * 60
MACRO_FEED_DEFAULT_DAYS = 31
# 政策解读属低频发布，用更长窗口避免整段为空
MACRO_FEED_POLICY_READING_DAYS = 365
_MACRO_FEED_MAX_ITEMS = 60

_feed_singleflight: AsyncSingleFlight[MacroFeedResponse] = AsyncSingleFlight()

# (响应字段, provider 方法, 中文标签)
_LIST_SOURCES = (
    ("releases", "fetch_latest_releases", "国家统计局发布"),
    ("policy_news", "fetch_pbc_news", "央行新闻发布"),
    ("policy_readings", "fetch_pbc_policy", "央行政策解读"),
)

# 利率卡片只展示最常看的期限，避免卡片过多
_SHIBOR_DISPLAY_TERMS = (("ON", "隔夜"), ("1W", "1周"), ("1M", "1月"), ("3M", "3月"))


def _get_nbs_provider():
    return get_provider("nbs")


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def _filter_recent(items: list[dict], *, days: int) -> list[dict]:
    cutoff = market_today() - timedelta(days=days)
    result = [
        item
        for item in items
        if (_parse_date(item.get("published_at")) or date.min) >= cutoff
    ]
    result.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    return result[:_MACRO_FEED_MAX_ITEMS]


def _to_feed_items(raw: list[dict]) -> list[MacroFeedItem]:
    return [
        MacroFeedItem(
            id=str(item.get("id") or item.get("url") or item.get("title") or ""),
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            published_at=str(item.get("published_at") or ""),
            source=str(item.get("source") or ""),
        )
        for item in raw
    ]


async def _fetch_list(method_name: str) -> list[dict]:
    provider = _get_nbs_provider()
    fetcher = getattr(provider, method_name)
    return await provider_gateway.call_blocking(
        "nbs",
        f"macro_feed_{method_name}",
        fetcher,
        semaphore=nbs_semaphore,
    )


def _extract_lpr_rates(rows: list[dict]) -> list[MacroRateItem]:
    ordered = sorted(rows, key=lambda row: str(row.get("TIME") or ""), reverse=True)
    if not ordered:
        return []
    latest, previous = ordered[0], (ordered[1] if len(ordered) > 1 else {})
    period = str(latest.get("TIME") or "")
    result: list[MacroRateItem] = []
    for field, label in (("LPR1Y", "LPR 1年期"), ("LPR5Y", "LPR 5年期")):
        value = _to_float(latest.get(field))
        if value is None:
            continue
        previous_value = _to_float(previous.get(field))
        result.append(
            MacroRateItem(
                key=field.lower(),
                label=label,
                value=value,
                period=period,
                change_bp=round((value - previous_value) * 100, 2) if previous_value is not None else None,
            )
        )
    return result


def _extract_shibor_rates(rows: list[dict]) -> list[MacroRateItem]:
    latest_by_term: dict[str, dict] = {}
    for row in rows:
        if not row.get("LATEST_RECORD"):
            continue
        latest_by_term[str(row.get("REPORT_PERIOD") or "")] = row
    result: list[MacroRateItem] = []
    for term, label in _SHIBOR_DISPLAY_TERMS:
        row = latest_by_term.get(term)
        if row is None:
            continue
        value = _to_float(row.get("IR_RATE"))
        if value is None:
            continue
        result.append(
            MacroRateItem(
                key=f"shibor_{term.lower()}",
                label=f"SHIBOR {label}",
                value=value,
                period=str(row.get("REPORT_DATE") or ""),
                change_bp=_to_float(row.get("CHANGE_RATE")),
            )
        )
    return result


async def _load_rates() -> list[MacroRateItem]:
    """复用宏观指标链路的 LPR/SHIBOR（含多源降级与 6 小时缓存）。"""
    lpr_rows: list[dict] = []
    shibor_rows: list[dict] = []
    try:
        lpr_rows = await _load_macro_metric("lpr")
    except Exception:
        logger.info("宏观利率 LPR 获取失败", exc_info=True)
    try:
        shibor_rows = await _load_macro_metric("shibor")
    except Exception:
        logger.info("宏观利率 SHIBOR 获取失败", exc_info=True)
    return [*_extract_lpr_rates(lpr_rows), *_extract_shibor_rates(shibor_rows)]


async def _load_macro_feed(days: int) -> MacroFeedResponse:
    outcomes = await asyncio.gather(
        *(_fetch_list(method_name) for _, method_name, _ in _LIST_SOURCES),
        return_exceptions=True,
    )
    sections: dict[str, list[dict]] = {}
    failed: list[str] = []
    for (source_key, _, label), outcome in zip(_LIST_SOURCES, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            failed.append(label)
            logger.warning("宏观列表源失败: source=%s error_type=%s", label, type(outcome).__name__)
            sections[source_key] = []
            continue
        window = MACRO_FEED_POLICY_READING_DAYS if source_key == "policy_readings" else days
        sections[source_key] = _filter_recent(outcome, days=window)

    rates = await _load_rates()

    total_items = sum(len(sections[key]) for key, _, _ in _LIST_SOURCES)
    if failed and total_items == 0 and not rates:
        status = "unavailable"
    elif failed:
        status = "partial"
    else:
        status = "available"

    today = market_today()
    return MacroFeedResponse(
        period_start=(today - timedelta(days=days)).isoformat(),
        period_end=today.isoformat(),
        releases=_to_feed_items(sections["releases"]),
        policy_news=_to_feed_items(sections["policy_news"]),
        policy_readings=_to_feed_items(sections["policy_readings"]),
        rates=rates,
        updated_at=market_now().isoformat(timespec="seconds"),
        status=status,
        failed_sources=failed,
    )


async def get_macro_feed(days: int = MACRO_FEED_DEFAULT_DAYS) -> MacroFeedResponse:
    """聚合国家统计局最新发布、央行新闻/政策解读与利率，结果缓存 15 分钟。"""
    days = max(1, min(int(days), 180))
    cache_key = dated_cache_key("macro_feed", days)
    cached = cache.get(cache_key)
    if cached is not None:
        return MacroFeedResponse.model_validate(cached)

    async def _load() -> MacroFeedResponse:
        result = await _load_macro_feed(days)
        cache.set(cache_key, result, ttl=MACRO_FEED_CACHE_TTL_SECONDS)
        return result

    return await _feed_singleflight.do(cache_key, _load)
