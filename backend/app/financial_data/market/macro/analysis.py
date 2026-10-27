"""宏观解读：按条目增量调用 LLM + 两级缓存，组装时间轴事件系列。

缓存策略（避免频繁调用大模型）：
- 每条宏观条目按 ``id|title|date`` 指纹缓存解读，历史条目不重复调用；
- 综述按"已解读条目指纹集合"缓存，仅在内容变化时重新生成；
- 两级：L1 进程内 ``analysis_cache``（快），L2 market 库 ``macro_analysis_cache``（跨重启/多 worker）；
- 缓存键与模型无关（全实例共享）：切换模型/子模型不会作废历史解读。

未解读的新条目标记为 ``pending``，前端展示原文，由后台预热任务补齐解读。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.core.cache import analysis_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.domain.timezones import market_now
from app.financial_data.market.macro.feed import MACRO_FEED_DEFAULT_DAYS, get_macro_feed
from app.financial_data.market.macro.schemas import (
    MacroAnalysisEvent,
    MacroAnalysisRef,
    MacroAnalysisResponse,
    MacroFeedItem,
    MacroFeedResponse,
)
from app.infrastructure.llm.sync_client import llm_chat
from app.infrastructure.persistence.macro_analysis_store import (
    load_macro_analysis,
    save_macro_analysis,
)

logger = logging.getLogger(__name__)

MACRO_ANALYSIS_PROMPT_VERSION = "v1"
_ITEM_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_SUMMARY_CACHE_TTL_SECONDS = 6 * 60 * 60
_MAX_ITEMS = 40
_BATCH_SIZE = 20

_analysis_singleflight: AsyncSingleFlight[MacroAnalysisResponse] = AsyncSingleFlight()
_prewarm_task: asyncio.Task[None] | None = None

_ITEM_SYSTEM_PROMPT = """你是资深宏观分析师。对给定的每条宏观资讯逐条解读，判断其对 A 股市场的影响。

## 输出要求
只返回严格 JSON，不要输出其他内容：
{
  "items": [
    {"index": 0, "category": "物价", "interpretation": "不超过 40 字的一句话解读，说明对市场/资产的含义", "impact": "偏多"}
  ]
}

## 字段说明
- index: 输入中的编号（从 0 开始），必须逐条对应，不得遗漏或杜撰
- category: 从「物价 / 经济增长 / 货币金融 / 外贸 / 就业 / 房地产 / 金融政策 / 其他」中选择
- interpretation: 一句话解读，点明对市场或资产的含义
- impact: 只能是「偏多 / 中性 / 偏空」

## 原则
- 基于给定事实判断，不做无依据推测
- 逐条对应，编号不得错位"""

_SUMMARY_SYSTEM_PROMPT = """你是资深宏观分析师。根据一组已解读的宏观事件，输出宏观综述与政策信号。

## 输出要求
只返回严格 JSON，不要输出其他内容：
{
  "summary": "2-3 句话总结近期宏观核心矛盾与对市场的影响",
  "sentiment": "中性",
  "policy_signals": ["政策信号1", "政策信号2"]
}

## 原则
- 只依据给定事件，不引入外部信息
- sentiment 只能是「偏多 / 中性 / 偏空」
- policy_signals 最多 5 条，每条不超过 20 字"""


@dataclass(frozen=True)
class _Interpretation:
    category: str
    interpretation: str
    impact: str
    pending: bool = False


@dataclass
class _ItemInterpretations:
    by_index: dict[int, _Interpretation]
    degraded: bool


def _cache_prefix(scope: str) -> str:
    """缓存前缀：只区分作用域与提示词版本，解读结果与所用模型无关。"""
    return f"macro_{scope}:{MACRO_ANALYSIS_PROMPT_VERSION}"


def _item_hash(item: MacroFeedItem) -> str:
    return hashlib.md5(f"{item.id}|{item.title}|{item.published_at}".encode()).hexdigest()


def _item_cache_keys(items: list[MacroFeedItem]) -> dict[int, str]:
    prefix = _cache_prefix("item")
    return {index: f"{prefix}:{_item_hash(item)}" for index, item in enumerate(items)}


async def _unresolved_indices(items: list[MacroFeedItem]) -> list[int]:
    """返回尚未命中 L1/L2 缓存的条目下标（即需要调用大模型的条目）。"""
    keys = _item_cache_keys(items)
    missing = [index for index in keys if cache.get(keys[index]) is None]
    if not missing:
        return []
    stored = await call_blocking(
        load_macro_analysis,
        [keys[index] for index in missing],
        max_age_seconds=_ITEM_CACHE_TTL_SECONDS,
        semaphore=database_semaphore,
    )
    return [index for index in missing if keys[index] not in stored]


def _normalize_impact(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in {"偏多", "中性", "偏空"} else "中性"


def _parse_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _collect_items(feed: MacroFeedResponse) -> list[MacroFeedItem]:
    items = [*feed.releases, *feed.policy_news, *feed.policy_readings]
    seen: set[str] = set()
    unique: list[MacroFeedItem] = []
    for item in items:
        key = _item_hash(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=lambda item: item.published_at, reverse=True)
    return unique[:_MAX_ITEMS]


async def _llm_interpret(entries: list[tuple[int, MacroFeedItem]]) -> dict[int, _Interpretation]:
    """一次 LLM 调用解读一批（新增）条目，返回 {原始下标: 解读}。"""
    lines = [
        f"[{position}] {item.published_at} [{item.source}] {item.title}"
        for position, (_, item) in enumerate(entries)
    ]
    prompt = "以下是最近的宏观资讯，请逐条解读：\n\n" + "\n".join(lines)
    raw = await llm_chat(
        [
            {"role": "system", "content": _ITEM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        json_format=True,
        task="macro_item",
    )
    payload = _parse_json(raw)
    rows = payload.get("items") if isinstance(payload, dict) else None
    result: dict[int, _Interpretation] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        position = row.get("index")
        if not isinstance(position, int) or not (0 <= position < len(entries)):
            continue
        original_index = entries[position][0]
        result[original_index] = _Interpretation(
            category=str(row.get("category") or "其他").strip() or "其他",
            interpretation=str(row.get("interpretation") or "").strip(),
            impact=_normalize_impact(row.get("impact")),
        )
    if not result:
        raise ValueError("宏观条目解读返回为空")
    return result


async def _interpret_items(items: list[MacroFeedItem], *, allow_llm: bool) -> _ItemInterpretations:
    keys = _item_cache_keys(items)
    resolved: dict[int, _Interpretation] = {}
    missing: list[int] = []

    for index, key in keys.items():
        cached = cache.get(key)
        if cached is not None:
            resolved[index] = _Interpretation(**cached)
        else:
            missing.append(index)

    # L2 持久化缓存（跨重启 / 多 worker）
    if missing:
        stored = await call_blocking(
            load_macro_analysis,
            [keys[index] for index in missing],
            max_age_seconds=_ITEM_CACHE_TTL_SECONDS,
            semaphore=database_semaphore,
        )
        still_missing: list[int] = []
        for index in missing:
            payload = stored.get(keys[index])
            if payload is None:
                still_missing.append(index)
                continue
            cache.set(keys[index], payload, ttl=_ITEM_CACHE_TTL_SECONDS)
            resolved[index] = _Interpretation(**payload)
        missing = still_missing

    degraded = False
    for start in range(0, len(missing), _BATCH_SIZE):
        if not allow_llm:
            break
        batch = missing[start : start + _BATCH_SIZE]
        try:
            fresh = await _llm_interpret([(index, items[index]) for index in batch])
        except Exception:
            degraded = True
            logger.warning("宏观条目解读失败，降级为原文：count=%s", len(batch), exc_info=True)
            continue
        entries: dict[str, dict] = {}
        for index, interpretation in fresh.items():
            resolved[index] = interpretation
            payload = {
                "category": interpretation.category,
                "interpretation": interpretation.interpretation,
                "impact": interpretation.impact,
            }
            cache.set(keys[index], payload, ttl=_ITEM_CACHE_TTL_SECONDS)
            entries[keys[index]] = payload
        if entries:
            try:
                await call_blocking(
                    save_macro_analysis,
                    entries,
                    retention_seconds=_ITEM_CACHE_TTL_SECONDS,
                    semaphore=database_semaphore,
                )
            except Exception:
                logger.warning("宏观条目解读持久化失败", exc_info=True)

    for index, item in enumerate(items):
        if index not in resolved:
            # 尚未解读（缓存未命中）：请求路径展示原文并标记待解读，交由后台预热补齐
            resolved[index] = _Interpretation(
                category="其他",
                interpretation=item.title,
                impact="中性",
                pending=True,
            )
    return _ItemInterpretations(by_index=resolved, degraded=degraded)


def _build_events(
    items: list[MacroFeedItem], interpretations: _ItemInterpretations
) -> list[MacroAnalysisEvent]:
    events: list[MacroAnalysisEvent] = []
    for index, item in enumerate(items):
        interpretation = interpretations.by_index.get(index)
        events.append(
            MacroAnalysisEvent(
                date=item.published_at,
                category=interpretation.category if interpretation else "其他",
                title=item.title,
                interpretation=interpretation.interpretation if interpretation else "",
                impact=interpretation.impact if interpretation else "中性",
                pending=bool(interpretation.pending) if interpretation else False,
                refs=[MacroAnalysisRef(title=item.title, url=item.url)] if item.url else [],
            )
        )
    events.sort(key=lambda event: event.date, reverse=True)
    return events


def _fallback_summary(events: list[MacroAnalysisEvent]) -> dict[str, Any]:
    counts = Counter(event.impact for event in events)
    if counts["偏多"] > counts["偏空"]:
        sentiment = "偏多"
    elif counts["偏空"] > counts["偏多"]:
        sentiment = "偏空"
    else:
        sentiment = "中性"
    return {
        "summary": (
            f"近 {len(events)} 条宏观事件中，偏多 {counts['偏多']} 条、偏空 {counts['偏空']} 条、"
            f"中性 {counts['中性']} 条。AI 综述暂不可用，详见下方事件时间轴。"
        ),
        "sentiment": sentiment,
        "policy_signals": [],
        "degraded": True,
    }


async def _llm_summarize(events: list[MacroAnalysisEvent]) -> dict[str, Any]:
    lines = [
        f"[{event.date}] ({event.category}/{event.impact}) {event.title} — {event.interpretation}"
        for event in events
    ]
    prompt = "以下是近期宏观事件及其解读，请输出综述与政策信号：\n\n" + "\n".join(lines)
    raw = await llm_chat(
        [
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        json_format=True,
    )
    payload = _parse_json(raw)
    if not isinstance(payload, dict) or not str(payload.get("summary") or "").strip():
        raise ValueError("宏观综述返回为空")
    signals = payload.get("policy_signals")
    return {
        "summary": str(payload.get("summary")).strip(),
        "sentiment": _normalize_impact(payload.get("sentiment")),
        "policy_signals": [str(item).strip() for item in signals[:5] if str(item).strip()]
        if isinstance(signals, list)
        else [],
        "degraded": False,
    }


async def _summarize(
    events: list[MacroAnalysisEvent], digest: str, *, allow_llm: bool
) -> tuple[dict[str, Any], bool]:
    key = f"{_cache_prefix('summary')}:{digest}"
    cached = cache.get(key)
    if cached is not None:
        return cached, True

    stored = await call_blocking(
        load_macro_analysis,
        [key],
        max_age_seconds=_SUMMARY_CACHE_TTL_SECONDS,
        semaphore=database_semaphore,
    )
    if key in stored:
        cache.set(key, stored[key], ttl=_SUMMARY_CACHE_TTL_SECONDS)
        return stored[key], True

    if not allow_llm:
        return _pending_summary(events), False

    try:
        summary = await _llm_summarize(events)
    except Exception:
        logger.warning("宏观综述生成失败，使用确定性汇总", exc_info=True)
        summary = _fallback_summary(events)

    cache.set(key, summary, ttl=_SUMMARY_CACHE_TTL_SECONDS)
    try:
        await call_blocking(
            save_macro_analysis,
            {key: summary},
            retention_seconds=_SUMMARY_CACHE_TTL_SECONDS,
            semaphore=database_semaphore,
        )
    except Exception:
        logger.warning("宏观综述持久化失败", exc_info=True)
    return summary, False


def _pending_summary(events: list[MacroAnalysisEvent]) -> dict[str, Any]:
    """已解读事件不足以生成综述时的占位：不标记 degraded，由 pending_count 提示。"""
    counts = Counter(event.impact for event in events)
    if counts["偏多"] > counts["偏空"]:
        sentiment = "偏多"
    elif counts["偏空"] > counts["偏多"]:
        sentiment = "偏空"
    else:
        sentiment = "中性"
    return {
        "summary": "",
        "sentiment": sentiment,
        "policy_signals": [],
        "degraded": False,
    }


def _empty_response(feed: MacroFeedResponse) -> MacroAnalysisResponse:
    return MacroAnalysisResponse(
        period=f"{feed.period_start} ~ {feed.period_end}",
        summary="近期暂无可解读的宏观事件。",
        sentiment="中性",
        events=[],
        policy_signals=[],
        generated_at=market_now().isoformat(timespec="seconds"),
    )


async def get_macro_analysis(days: int = MACRO_FEED_DEFAULT_DAYS) -> MacroAnalysisResponse:
    """对近期宏观事件做 AI 解读并梳理为时间轴，历史条目走缓存不重复调用大模型。"""
    feed = await get_macro_feed(days)
    items = _collect_items(feed)
    if not items:
        return _empty_response(feed)

    feed_hash = hashlib.md5("|".join(_item_hash(item) for item in items).encode()).hexdigest()
    singleflight_key = f"{_cache_prefix('response')}:{feed_hash}"

    async def _load() -> MacroAnalysisResponse:
        interpretations = await _interpret_items(items, allow_llm=False)
        events = _build_events(items, interpretations)
        resolved_events = [event for event in events if not event.pending]
        if resolved_events:
            # 综述只依据已解读事件；待解读条目补齐后 digest 变化会自动重算
            resolved_hash = hashlib.md5(
                "|".join(
                    _item_hash(items[index])
                    for index, item in enumerate(items)
                    if not interpretations.by_index[index].pending
                ).encode()
            ).hexdigest()
            summary, summary_cached = await _summarize(
                resolved_events, resolved_hash, allow_llm=False
            )
        else:
            summary = _pending_summary([])
            summary["summary"] = "近期宏观事件正在解读中，稍后刷新即可查看 AI 综述。"
            summary_cached = False
        degraded = bool(summary.get("degraded")) or interpretations.degraded
        pending_count = sum(1 for event in events if event.pending)
        if degraded:
            warning = "AI 解读暂不可用，当前展示原文与确定性汇总。"
        elif pending_count:
            warning = f"{pending_count} 条最新宏观事件仍在后台解读，请稍后刷新查看 AI 综述。"
        else:
            warning = ""
        return MacroAnalysisResponse(
            period=f"{feed.period_start} ~ {feed.period_end}",
            summary=str(summary.get("summary") or ""),
            sentiment=_normalize_impact(summary.get("sentiment")),
            events=events,
            policy_signals=list(summary.get("policy_signals") or []),
            degraded=degraded,
            pending_count=pending_count,
            warning=warning,
            generated_at=market_now().isoformat(timespec="seconds"),
            cached=summary_cached,
        )

    return await _analysis_singleflight.do(singleflight_key, _load)


async def prewarm_macro_analysis(days: int = MACRO_FEED_DEFAULT_DAYS) -> int:
    """后台预热：为尚未解读的宏观条目补齐解读，并生成 AI 综述。

    已命中缓存的条目不会重复调用大模型；返回本次新完成解读的条目数。
    各类大模型异常在内部消化（降级为原文），不会抛出。
    """
    feed = await get_macro_feed(days)
    items = _collect_items(feed)
    if not items:
        return 0
    pending_before = await _unresolved_indices(items)
    interpretations = await _interpret_items(items, allow_llm=True)
    if pending_before:
        events = _build_events(items, interpretations)
        resolved_events = [event for event in events if not event.pending]
        if resolved_events:
            resolved_hash = hashlib.md5(
                "|".join(
                    _item_hash(items[index])
                    for index, item in enumerate(items)
                    if not interpretations.by_index[index].pending
                ).encode()
            ).hexdigest()
            await _summarize(resolved_events, resolved_hash, allow_llm=True)
    pending_after = await _unresolved_indices(items)
    return max(0, len(pending_before) - len(pending_after))


def trigger_macro_prewarm(days: int = MACRO_FEED_DEFAULT_DAYS) -> bool:
    """命中待解读条目时在后台补齐解读，请求线程只调度不等待。

    与 ``_start_us_macro_refresh`` 同一模式：同一时刻只保留一个预热任务，
    已有任务在跑时直接返回 ``False``。``asyncio.create_task`` 会复制当前上下文，
    因此该任务会沿用发起请求的用户模型/子模型配置。
    """
    global _prewarm_task
    if _prewarm_task is not None and not _prewarm_task.done():
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 无事件循环（如脚本直调）时静默跳过
        return False
    task = loop.create_task(prewarm_macro_analysis(days), name="macro_analysis_prewarm")
    _prewarm_task = task

    def _finish(finished: asyncio.Task[None]) -> None:
        global _prewarm_task
        try:
            finished.result()
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - 后台预热失败不影响请求
            logger.warning("宏观解读后台预热失败", exc_info=True)
        finally:
            _prewarm_task = None

    task.add_done_callback(_finish)
    return True


__all__ = [
    "get_macro_analysis",
    "prewarm_macro_analysis",
    "trigger_macro_prewarm",
    "MACRO_ANALYSIS_PROMPT_VERSION",
]
