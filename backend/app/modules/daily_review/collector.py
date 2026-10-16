"""Date-aware market data collection for daily reviews."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

from app.core.market import market_today
from app.core.news import dedupe_news_items
from app.domain.market import IndexItem, MarketIndices
from app.domain.news import NewsSearchItem
from app.financial_data.market.public import (
    NorthboundHistoryPoint,
    get_dragon_tiger_list,
    get_hot_stocks,
    get_index_kline,
    get_indices,
    get_limit_break_pool,
    get_limit_up_ladder,
    get_macro_analysis,
    get_macro_data,
    get_market_news,
    get_market_statistics,
    get_market_volume_stats,
    get_northbound_history,
    get_ths_hot_concept,
    get_ths_hot_industry,
)
from app.modules.daily_review.models import DailyReviewSourceStatus, PolicyNewsSnapshotItem
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
    # 已排序分类的政策新闻（与 snapshot.policy_news 同源）；提前算好，
    # 避免 review_builder.build_snapshot 再对同一份新闻重复分类一次。
    policy_news: list[PolicyNewsSnapshotItem] = field(default_factory=list)


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


async def _target_northbound(target_date: date) -> tuple[NorthboundHistoryPoint, str]:
    """返回（北向资金点位, 降级说明）；复盘日未披露时退化为最近一个已披露交易日。"""
    date_text = target_date.isoformat()
    try:
        response = await get_northbound_history(500)
    except Exception as error:
        raise HistoricalReviewDataUnavailableError(f"北向资金接口异常: {error}") from error
    point = next((item for item in response.items if item.date == date_text), None)
    if point is not None:
        return point, ""
    latest = max(
        (item for item in response.items if item.date and item.date <= date_text),
        key=lambda item: item.date,
        default=None,
    )
    if latest is None:
        raise HistoricalReviewDataUnavailableError("复盘日及之前均无北向资金数据")
    return latest, f"复盘日 {date_text} 未披露北向资金，已回退最近交易日 {latest.date}"


def _historical_unavailable(label: str) -> HistoricalReviewDataUnavailableError:
    return HistoricalReviewDataUnavailableError(f"{label}不支持历史回溯，未使用当前数据替代")


def _data_date(value: Any, target_date: str, is_realtime: bool) -> str:
    """尽量给出数据真实归属日期；榜单类无自带日期时标注实际抓取日。"""
    direct = getattr(value, "date", None)
    if direct:
        return str(direct)
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            candidate = (
                first.get("trade_date") or first.get("date") or first.get("publish_time") or first.get("time")
            )
        else:
            candidate = (
                getattr(first, "trade_date", None)
                or getattr(first, "date", None)
                or getattr(first, "publish_time", None)
            )
        if candidate:
            return str(candidate)[:10]
        # 热门榜类快照本身不带日期：历史复盘必须暴露这是「当前快照」，
        # 而不是复盘日数据。
        return market_today().isoformat()
    if isinstance(value, dict) and value:
        return _macro_period(value) or market_today().isoformat()
    return target_date if is_realtime else ""


def _macro_period(macro_data: dict) -> str:
    """取宏观数据里最新的统计口径（形如 2026-09），没有则返回空串。"""
    periods: list[str] = []
    for indicator in macro_data.values():
        latest = indicator.get("latest") if isinstance(indicator, dict) else None
        period = latest.get("TIME") if isinstance(latest, dict) else None
        if period:
            periods.append(str(period)[:10])
    return max(periods, default="")


def _clip_macro_analysis(value: Any, target_text: str) -> Any:
    """丢弃复盘日之后的宏观事件；未发生截断时原样返回，避免改写共享缓存对象。"""
    if value is None or isinstance(value, BaseException):
        return value
    events = list(getattr(value, "events", None) or [])
    clipped = [
        event
        for event in events
        if not getattr(event, "date", "") or str(event.date) <= target_text
    ]
    if len(clipped) == len(events):
        return value
    pending_count = sum(1 for event in clipped if getattr(event, "pending", False))
    return value.model_copy(update={"events": clipped, "pending_count": pending_count})


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
        "macro_analysis": get_macro_analysis(),
        "limit_up_ladder": get_limit_up_ladder(target_date),
        # 炸板池用于计算炸板率（封板质量），上游只有 fuyao 提供，失败时只是缺失该锚点。
        "limit_break_pool": get_limit_break_pool(target_date),
        "northbound_funds": _target_northbound(target_date),
    }
    names = list(coroutines)
    resolved = await asyncio.gather(*coroutines.values(), return_exceptions=True)
    values = dict(zip(names, resolved, strict=True))
    northbound = values.get("northbound_funds")
    northbound_fallback_note = ""
    if isinstance(northbound, tuple):
        northbound_point, northbound_fallback_note = northbound
        values["northbound_funds"] = northbound_point
    # 复盘日之后的宏观事件不能进入历史复盘，否则会引用「未来」事件。
    values["macro_analysis"] = _clip_macro_analysis(values.get("macro_analysis"), target_date.isoformat())
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
    policy_news = classify_policy_news(filtered_news, target_date=target_date)
    web_search_used = len(filtered_news) < 8 or len(policy_news) < 3
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
        if filtered_web_news:
            # 引入 Web Search 结果后必须重新分类，否则新增政策事件会被漏掉。
            policy_news = classify_policy_news(filtered_news, target_date=target_date)
    values["market_news"] = filtered_news
    target_text = target_date.isoformat()
    statuses = {
        name: _status(name, value, target_text, use_realtime)
        for name, value in values.items()
    }
    if northbound_fallback_note:
        statuses["northbound_funds"] = DailyReviewSourceStatus(
            status="partial",
            requested_date=target_text,
            data_date=_data_date(values.get("northbound_funds"), target_text, use_realtime),
            provider="北向资金",
            is_realtime=use_realtime,
            error=northbound_fallback_note,
        )
    macro_analysis_value = values.get("macro_analysis")
    if not isinstance(macro_analysis_value, Exception) and macro_analysis_value is not None:
        pending_count = int(getattr(macro_analysis_value, "pending_count", 0) or 0)
        degraded = bool(getattr(macro_analysis_value, "degraded", False))
        if degraded and pending_count:
            macro_error = f"AI 宏观解读降级，{pending_count} 条事件展示原文待解读"
        elif degraded:
            macro_error = "AI 宏观解读暂不可用，已使用确定性汇总"
        elif pending_count:
            macro_error = f"{pending_count} 条宏观事件待后台解读，暂展示原文"
        else:
            macro_error = ""
        statuses["macro_analysis"] = DailyReviewSourceStatus(
            status="partial" if (degraded or pending_count) else "complete",
            requested_date=target_text,
            data_date=target_text if use_realtime else "",
            provider="AI 宏观解读",
            is_realtime=use_realtime,
            error=macro_error,
        )
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
    return DailyReviewCollection(values=values, source_status=statuses, policy_news=policy_news)
