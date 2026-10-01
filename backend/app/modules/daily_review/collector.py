"""Date-aware market data collection for daily reviews."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from app.core.news import dedupe_news_items
from app.domain.market import IndexItem, MarketIndices
from app.domain.news import NewsSearchItem
from app.financial_data.market.public import (
    get_dragon_tiger_list,
    get_hot_stocks,
    get_index_kline,
    get_indices,
    get_limit_up_ladder,
    get_macro_data,
    get_market_news,
    get_market_statistics,
    get_market_volume_stats,
    get_northbound_history,
    get_ths_hot_concept,
    get_ths_hot_industry,
)
from app.modules.daily_review.models import DailyReviewSourceStatus
from app.modules.daily_review.news_policy import classify_policy_news, filter_news_for_review
from app.modules.daily_review.web_policy_news import search_financial_policy_news

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
        change_pct = bar.change_pct
        if change_pct is None and bar.pre_close and bar.pre_close > 0 and bar.close is not None:
            change_pct = round((bar.close - bar.pre_close) / bar.pre_close * 100, 2)
        amplitude = bar.amplitude
        if amplitude is None and bar.pre_close and bar.pre_close > 0 and bar.high is not None and bar.low is not None:
            amplitude = round((bar.high - bar.low) / bar.pre_close * 100, 2)
        items.append(IndexItem(
            code=code,
            name=name,
            price=bar.close,
            change_pct=change_pct,
            volume=bar.volume,
            amount=bar.amount,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            amplitude=amplitude,
            pre_close=bar.pre_close,
        ))
        if result.source and result.source not in sources:
            sources.append(result.source)
    if not items:
        raise HistoricalReviewDataUnavailableError("历史指数数据不可用")
    return MarketIndices(date=date_text, indices=items, source=" / ".join(sources))


async def _target_northbound(target_date: date):
    date_text = target_date.isoformat()
    try:
        response = await get_northbound_history(500)
        point = next((item for item in response.items if item.date == date_text), None)
        if point is not None:
            return point
    except Exception as error:
        raise HistoricalReviewDataUnavailableError(f"北向资金接口异常: {error}") from error
    raise HistoricalReviewDataUnavailableError("当日北向资金数据不可用（可能非交易日或未披露）")


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
    coroutines = {
        "indices": get_indices() if use_realtime else _historical_indices(target_date),
        "hot_stocks": get_hot_stocks(),
        "hot_concepts": get_ths_hot_concept(),
        "hot_industries": get_ths_hot_industry(),
        "dragon_tiger": get_dragon_tiger_list(target_date.isoformat()),
        "market_statistics": get_market_statistics(target_date.isoformat()),
        "market_news": get_market_news(),
        "market_volume": get_market_volume_stats(target_date, use_realtime=use_realtime),
        "macro_data": get_macro_data(),
        "limit_up_ladder": get_limit_up_ladder(target_date),
        "northbound_funds": _target_northbound(target_date),
    }
    names = list(coroutines)
    resolved = await asyncio.gather(*coroutines.values(), return_exceptions=True)
    values = dict(zip(names, resolved, strict=True))
    market_news = values.get("market_news")
    local_news_error = market_news if isinstance(market_news, BaseException) else None
    local_news = (
        []
        if local_news_error is not None or market_news is None
        else cast(list[NewsSearchItem], market_news)
    )
    filtered_news = filter_news_for_review(
        local_news,
        target_date,
        use_realtime=use_realtime,
    )
    policy_count = len(classify_policy_news(filtered_news, target_date=target_date))
    web_search_used = len(filtered_news) < 8 or policy_count < 3
    web_news_count = 0
    if web_search_used:
        web_news = await search_financial_policy_news(target_date)
        filtered_web_news = filter_news_for_review(
            web_news,
            target_date,
            use_realtime=False,
        )
        web_news_count = len(filtered_web_news)
        filtered_news = cast(
            list[NewsSearchItem],
            dedupe_news_items([*filtered_news, *filtered_web_news]),
        )[:40]
    values["market_news"] = filtered_news
    target_text = target_date.isoformat()
    statuses = {
        name: _status(name, value, target_text, use_realtime)
        for name, value in values.items()
    }
    if values.get("market_news") == []:
        statuses["market_news"] = DailyReviewSourceStatus(
            status="unavailable",
            requested_date=target_text,
            is_realtime=use_realtime,
            error="复盘日前后 2 天没有可核验发布时间的本地或 Web Search 财经政策新闻",
        )
    elif local_news_error is not None:
        statuses["market_news"] = DailyReviewSourceStatus(
            status="partial",
            requested_date=target_text,
            data_date=_data_date(filtered_news, target_text, use_realtime),
            provider="Web Search",
            is_realtime=use_realtime,
            error=f"内置财经新闻不可用，已使用 Web Search 补充：{local_news_error}",
        )
    elif web_search_used and web_news_count > 0:
        statuses["market_news"] = DailyReviewSourceStatus(
            status="complete",
            requested_date=target_text,
            data_date=_data_date(filtered_news, target_text, use_realtime),
            provider="内置财经新闻 + Web Search",
            is_realtime=use_realtime,
        )
    elif web_search_used:
        statuses["market_news"] = DailyReviewSourceStatus(
            status="partial",
            requested_date=target_text,
            data_date=_data_date(filtered_news, target_text, use_realtime),
            provider="内置财经新闻",
            is_realtime=use_realtime,
            error="内置新闻数量或重点事件不足，已尝试 Web Search，但没有取得带可核验发布日期的补充结果",
        )
    return DailyReviewCollection(values=values, source_status=statuses)
