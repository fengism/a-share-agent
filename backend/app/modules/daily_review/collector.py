"""Date-aware market data collection for daily reviews."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.domain.market import IndexItem, MarketIndices, MarketVolume
from app.financial_data.market.public import (
    get_dragon_tiger_list,
    get_hot_stocks,
    get_index_kline,
    get_indices,
    get_macro_data,
    get_market_news,
    get_market_statistics,
    get_market_volume,
    get_realtime_market_volume,
    get_ths_hot_concept,
    get_ths_hot_industry,
)
from app.modules.daily_review.models import DailyReviewSourceStatus

_CORE_INDICES = (
    ("000001", "上证指数"),
    ("399001", "深证成指"),
    ("399006", "创业板指"),
    ("000688", "科创50"),
)


class HistoricalReviewDataUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyReviewCollection:
    values: dict[str, Any]
    source_status: dict[str, DailyReviewSourceStatus]


async def _historical_indices(target_date: date) -> MarketIndices:
    date_text = target_date.isoformat()
    results = await asyncio.gather(
        *(get_index_kline(code, start_date=date_text, end_date=date_text) for code, _ in _CORE_INDICES),
        return_exceptions=True,
    )
    items: list[IndexItem] = []
    sources: list[str] = []
    for (code, name), result in zip(_CORE_INDICES, results, strict=True):
        if isinstance(result, BaseException):
            if not isinstance(result, Exception):
                raise result
            continue
        if not result.items:
            continue
        bar = next((item for item in reversed(result.items) if item.date == date_text), None)
        if bar is None:
            continue
        items.append(IndexItem(
            code=code,
            name=name,
            price=bar.close,
            change_pct=bar.change_pct,
            volume=bar.volume,
            amount=bar.amount,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            amplitude=bar.amplitude,
            pre_close=bar.pre_close,
        ))
        if result.source and result.source not in sources:
            sources.append(result.source)
    if not items:
        raise HistoricalReviewDataUnavailableError("历史指数数据不可用")
    return MarketIndices(date=date_text, indices=items, source=" / ".join(sources))


async def _historical_market_volume(target_date: date) -> MarketVolume:
    date_text = target_date.isoformat()
    response = await get_market_volume(date_text, date_text)
    item = next((row for row in response.items if row.date == date_text), None)
    if item is None:
        raise HistoricalReviewDataUnavailableError("历史成交额数据不可用")
    return MarketVolume(date=date_text, amount=item.amount)


def _historical_unavailable(label: str) -> HistoricalReviewDataUnavailableError:
    return HistoricalReviewDataUnavailableError(f"{label}不支持历史回溯，未使用当前数据替代")


def _data_date(value: Any, target_date: str, is_realtime: bool) -> str:
    direct = getattr(value, "date", None)
    if direct:
        return str(direct)
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            candidate = first.get("trade_date") or first.get("date") or first.get("publish_time")
        else:
            candidate = getattr(first, "trade_date", None) or getattr(first, "date", None)
        if candidate:
            return str(candidate)[:10]
    return target_date if is_realtime else ""


def _provider(value: Any) -> str:
    source = getattr(value, "source", None)
    if source:
        return str(source)
    if isinstance(value, dict):
        return str(value.get("source") or "")
    return ""


def _status(name: str, value: Any, target_date: str, is_realtime: bool) -> DailyReviewSourceStatus:
    if isinstance(value, Exception):
        return DailyReviewSourceStatus(
            status="unavailable",
            requested_date=target_date,
            is_realtime=is_realtime,
            error=str(value) or f"{name}不可用",
        )
    partial = bool(getattr(value, "partial", False))
    return DailyReviewSourceStatus(
        status="partial" if partial else "complete",
        requested_date=target_date,
        data_date=_data_date(value, target_date, is_realtime),
        provider=_provider(value),
        is_realtime=is_realtime,
    )


async def collect_daily_review_data(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
    if use_realtime:
        coroutines = {
            "indices": get_indices(),
            "hot_stocks": get_hot_stocks(),
            "hot_concepts": get_ths_hot_concept(),
            "hot_industries": get_ths_hot_industry(),
            "dragon_tiger": get_dragon_tiger_list(target_date.isoformat()),
            "market_statistics": get_market_statistics(target_date.isoformat()),
            "market_news": get_market_news(),
            "market_volume": get_realtime_market_volume(),
            "macro_data": get_macro_data(),
        }
    else:
        coroutines = {
            "indices": _historical_indices(target_date),
            "dragon_tiger": get_dragon_tiger_list(target_date.isoformat()),
            "market_statistics": get_market_statistics(target_date.isoformat()),
            "market_volume": _historical_market_volume(target_date),
        }
    names = list(coroutines)
    resolved = await asyncio.gather(*coroutines.values(), return_exceptions=True)
    values = dict(zip(names, resolved, strict=True))
    if not use_realtime:
        values.update({
            "hot_stocks": _historical_unavailable("热门股票"),
            "hot_concepts": _historical_unavailable("热点概念"),
            "hot_industries": _historical_unavailable("热点行业"),
            "market_news": _historical_unavailable("市场新闻"),
            "macro_data": _historical_unavailable("宏观数据"),
        })
    target_text = target_date.isoformat()
    statuses = {
        name: _status(name, value, target_text, use_realtime)
        for name, value in values.items()
    }
    return DailyReviewCollection(values=values, source_status=statuses)
