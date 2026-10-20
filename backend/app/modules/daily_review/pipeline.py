import asyncio
import contextlib
import hashlib
import json
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal, cast

from pydantic import ValidationError

from app.configuration import get_effective_settings
from app.configuration.schema import Settings
from app.core.cache import analysis_cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.progress import ProgressCallback, ProgressEmitter
from app.core.timezones import SHANGHAI_TIMEZONE
from app.domain.llm import LLMConfigurationError
from app.domain.prompting import PromptTrace
from app.financial_data.market.public import (
    get_completed_market_date,
    get_macro_analysis,
    get_market_date_on_or_before,
)
from app.infrastructure.llm.prompting import PromptExecutionError, PromptRun, run_structured_prompt
from app.modules.daily_review import review_builder
from app.modules.daily_review.collector import DailyReviewCollection, collect_daily_review_data
from app.modules.daily_review.cycle_store import (
    build_cycle_record,
    previous_cycle_record,
    recent_cycle_records,
    save_cycle_record,
)
from app.modules.daily_review.cycle_trend import build_cycle_trend
from app.modules.daily_review.models import (
    DAILY_REVIEW_SCHEMA_VERSION,
    CycleTrend,
    DailyReviewCycleRecord,
    DailyReviewDataSnapshot,
    DailyReviewPreviousCheck,
    DailyReviewResult,
    DailyReviewSentimentCycle,
    DailyReviewWatchItem,
)
from app.modules.daily_review.persistence.repository import load_daily_review, save_daily_review
from app.modules.daily_review.prompts import (
    DAILY_REVIEW_PROMPT_SPEC,
    MARKET_USER_PROMPT,
    DailyReviewPromptOutput,
)
from app.modules.daily_review.report_renderer import render_daily_review_markdown
from app.modules.daily_review.schemas import DailyReviewRequest
from app.modules.daily_review.self_check import build_previous_review_check

logger = logging.getLogger(__name__)
# 生成过程向调用方（Workflow / 流式接口）回报的阶段事件。
DailyReviewProgressCallback = ProgressCallback[dict[str, Any]]
_QUEUE_MESSAGE = "已受理每日复盘任务，正在排队"
_COLLECT_MESSAGE = "正在采集行情、资金、新闻与宏观数据…"
_ANALYZE_MESSAGE = "数据采集完成，正在生成 AI 复盘报告…"
_PERSIST_MESSAGE = "正在校验并保存复盘报告…"
_LLM_FALLBACK_RETRY_COOLDOWN = timedelta(minutes=10)
_MACRO_READY_RETRY_COOLDOWN = timedelta(minutes=10)
_THIN_NEWS_RETRY_COOLDOWN = timedelta(hours=6)
_NEWS_UNAVAILABLE_MARKERS = (
    "有效发布时间",
    "复盘时点附近",
    "未使用当前新闻替代",
    "Web Search 财经政策新闻",
)
# 跨用户共享：同一有效交易日的采集快照与用户、模型无关。
# 历史口径复用 15 分钟；当日收盘口径用更长的 TTL（见下），避免晚间重复采集。
_COLLECTION_CACHE_TTL_SECONDS = 15 * 60.0
# 收盘后当日口径（use_realtime）数据已定型：快照可长时间复用，
# 既避免晚间多用户重复采集，也让后台预热生成的 Prompt 稳定命中输出缓存。
_SETTLED_COLLECTION_CACHE_TTL_SECONDS = 4 * 60 * 60.0
# 同一 Prompt（含 Prompt 版本与所用模型）的复盘输出复用 6 小时，避免重复 1-3 分钟的 LLM 调用。
_REVIEW_LLM_CACHE_TTL_SECONDS = 6 * 60 * 60.0
# 情绪周期趋势回看的交易日数量。
_CYCLE_TREND_DAYS = 20

# 同一（有效交易日, 用户）的生成串行化：Bot 直呼与 Web 工作流同时触发时，
# 后来者等前一次写库完成后命中缓存直接返回，避免双份采集与双份长耗时 LLM 调用。
_generation_locks: dict[tuple[str, int], asyncio.Lock] = {}
_generation_locks_guard = asyncio.Lock()
# 同一 Prompt（同日 + 同模型）的在途 LLM 调用串行化：多个用户同时首次生成时，
# 后来者在锁内二次检查输出缓存，从而只真实调用一次 LLM。
_prompt_locks: dict[str, asyncio.Lock] = {}


async def _generation_lock(key: tuple[str, int]) -> asyncio.Lock:
    async with _generation_locks_guard:
        return _generation_locks.setdefault(key, asyncio.Lock())


async def _prompt_lock(key: str) -> asyncio.Lock:
    async with _generation_locks_guard:
        return _prompt_locks.setdefault(key, asyncio.Lock())


def _collection_cache_key(resolution: "DailyReviewDateResolution") -> str:
    return f"daily_review_collection:{resolution.effective_date.isoformat()}"


_HEARTBEAT_INTERVAL_SECONDS = 5.0


async def _stage_started(progress: ProgressEmitter[dict[str, Any]], stage: str, message: str) -> None:
    await progress.emit({"type": "stage_started", "stage": stage, "message": message})


async def _stage_completed(
    progress: ProgressEmitter[dict[str, Any]],
    stage: str,
    message: str = "",
    **extra: Any,
) -> None:
    await progress.emit({"type": "stage_completed", "stage": stage, "message": message, **extra})


async def _stage_failed(progress: ProgressEmitter[dict[str, Any]], stage: str, message: str) -> None:
    await progress.emit({"type": "stage_failed", "stage": stage, "message": message})


@asynccontextmanager
async def _stage_heartbeat(
    progress: ProgressEmitter[dict[str, Any]],
    stage: str,
    label: str,
    *,
    interval: float = _HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncGenerator[None, None]:
    """长耗时阶段的心跳：让前端能看到「已用 Ns」，而不是一行不动的文字。

    复盘的分析阶段是一次非流式结构化调用（可长达分钟级），期间没有任何中间事件。
    """
    if progress.callback is None:
        yield
        return
    started_at = time.monotonic()
    stop = asyncio.Event()

    async def beat() -> None:
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                await progress.emit({
                    "type": "stage_progress",
                    "stage": stage,
                    "message": f"{label}…（已用 {int(time.monotonic() - started_at)}s）",
                    "elapsed_ms": int((time.monotonic() - started_at) * 1000),
                })

    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _collect_shared(
    resolution: "DailyReviewDateResolution",
    progress: ProgressEmitter[dict[str, Any]] | None = None,
) -> DailyReviewCollection:
    """采集复盘数据；同一有效交易日的快照跨用户共享。

    历史口径复用 15 分钟，期间新增的新闻 / 宏观事件会在下一次采集时体现；
    收盘后的当日口径（use_realtime=True）行情已定型，用更长 TTL 复用，
    让晚间多用户与后台预热共用同一份 Prompt（从而命中输出缓存）。
    """
    key = _collection_cache_key(resolution)
    cached = analysis_cache.get(key)
    if cached is not None:
        logger.info("复用复盘采集快照: date=%s", resolution.effective_date.isoformat())
        return cast(DailyReviewCollection, cached)
    collection = await collect_daily_review_data(
        resolution.effective_date,
        use_realtime=resolution.use_realtime,
        progress_callback=progress.emit if progress is not None else None,
    )
    ttl = (
        _SETTLED_COLLECTION_CACHE_TTL_SECONDS
        if resolution.use_realtime
        else _COLLECTION_CACHE_TTL_SECONDS
    )
    analysis_cache.set(key, collection, ttl)
    return collection


def _review_llm_cache_key(user_content: str) -> str:
    """复盘 LLM 输出缓存 key：只取决于提示词内容与 Prompt 版本。

    与个股分析、产业链、宏观解读保持一致：**AI 分析结果缓存与所用模型无关**。
    换模型不会另起一份缓存；需要强制重新生成时由 ``force`` 跳过缓存。
    """
    material = json.dumps(
        {"ref": DAILY_REVIEW_PROMPT_SPEC.ref, "prompt": user_content},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"daily_review_llm:{hashlib.sha256(material.encode()).hexdigest()}"


def _cached_prompt_run(cached: object) -> PromptRun[DailyReviewPromptOutput] | None:
    if not isinstance(cached, dict):
        return None
    output = cached.get("output")
    trace = cached.get("trace")
    if output is None or trace is None:
        return None
    try:
        return PromptRun(
            value=DailyReviewPromptOutput.model_validate(output),
            trace=PromptTrace.model_validate(trace),
        )
    except ValidationError:
        logger.warning("复盘 LLM 缓存反序列化失败，改为重新生成", exc_info=True)
        return None


async def _run_review_prompt(
    user_content: str,
    settings: Settings,
    *,
    allow_cache: bool,
) -> PromptRun[DailyReviewPromptOutput]:
    """执行结构化复盘 Prompt；相同 Prompt 的输出跨用户复用（与模型无关）。"""
    key = _review_llm_cache_key(user_content)
    if allow_cache:
        cached_run = _cached_prompt_run(analysis_cache.get(key))
        if cached_run is not None:
            logger.info("复用同一 Prompt 的复盘生成结果")
            return cached_run
    return await _generate_review_prompt(key, user_content, settings, allow_cache=allow_cache)


async def _generate_review_prompt(
    key: str,
    user_content: str,
    settings: Settings,
    *,
    allow_cache: bool,
) -> PromptRun[DailyReviewPromptOutput]:
    """在锁内二次检查缓存后真正调用 LLM，避免多用户重复调用同一 Prompt。"""
    lock = await _prompt_lock(key)
    async with lock:
        if allow_cache:
            cached_run = _cached_prompt_run(analysis_cache.get(key))
            if cached_run is not None:
                logger.info("复用同一 Prompt 的复盘生成结果（等待在途调用完成）")
                return cached_run
        prompt_run = await run_structured_prompt(
            DAILY_REVIEW_PROMPT_SPEC,
            {"prompt": user_content},
            settings=settings,
            max_tokens=settings.analysis_llm_max_completion_tokens,
            timeout_seconds=settings.analysis_llm_timeout_seconds,
        )
        analysis_cache.set(
            key,
            {
                "output": prompt_run.value.model_dump(mode="json"),
                "trace": prompt_run.trace.model_dump(mode="json"),
            },
            _REVIEW_LLM_CACHE_TTL_SECONDS,
        )
        return prompt_run


def _parse_generated_at(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        logger.warning("复盘生成时间无法解析，跳过缓存失效冷却判断: %r", value)
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SHANGHAI_TIMEZONE)
    return parsed.astimezone(SHANGHAI_TIMEZONE)


def _older_than(value: str, delta: timedelta) -> bool:
    parsed = _parse_generated_at(value)
    if parsed is None:
        return False
    return _local_now() - parsed >= delta


def _llm_config_error(review: DailyReviewResult) -> bool:
    return "API Key" in review.llm_error or "api key" in review.llm_error.lower()


async def _macro_analysis_staleness(review: DailyReviewResult) -> str | None:
    """宏观解读补齐后，让旧复盘自动重算（带冷却，避免后台未就绪时反复重算）。"""
    cached_macro = review.data_snapshot.macro_analysis or {}
    incomplete = (
        not cached_macro
        or bool(cached_macro.get("pending_count"))
        or bool(cached_macro.get("degraded"))
    )
    if not incomplete or not _older_than(review.generated_at, _MACRO_READY_RETRY_COOLDOWN):
        return None
    try:
        current = await get_macro_analysis()
    except Exception:
        logger.warning("读取宏观解读状态失败，跳过复盘缓存失效判断", exc_info=True)
        return None
    if not current.events or current.pending_count or current.degraded:
        return None
    return "macro_analysis_ready"


async def _cached_review_staleness(review: DailyReviewResult) -> str | None:
    """返回缓存复盘需要重算的原因；None 表示可以直接复用。"""
    if review.schema_version < DAILY_REVIEW_SCHEMA_VERSION:
        return "schema_outdated"
    if (
        review.generation_status == "fallback"
        and not _llm_config_error(review)
        and _older_than(review.generated_at, _LLM_FALLBACK_RETRY_COOLDOWN)
    ):
        return "llm_fallback"
    stale_reason = await _macro_analysis_staleness(review)
    if stale_reason is not None:
        return stale_reason
    status = review.data_snapshot.source_status.get("market_news")
    if status is None:
        return None
    if status.status == "unavailable" and any(marker in status.error for marker in _NEWS_UNAVAILABLE_MARKERS):
        return "market_news_unavailable"
    if (
        status.status == "partial"
        and not review.data_snapshot.policy_news
        and _older_than(review.generated_at, _THIN_NEWS_RETRY_COOLDOWN)
    ):
        return "news_policy_empty"
    return None


@dataclass(frozen=True)
class DailyReviewDateResolution:
    requested_date: date
    effective_date: date
    session_status: Literal["completed", "adjusted"]
    use_realtime: bool


def _local_now() -> datetime:
    return datetime.now(SHANGHAI_TIMEZONE)


async def resolve_daily_review_date(
    requested_date: date | None,
    *,
    now: datetime | None = None,
) -> DailyReviewDateResolution:
    local_now = (now or _local_now()).astimezone(SHANGHAI_TIMEZONE)
    requested = requested_date or local_now.date()
    if requested > local_now.date():
        raise ValueError("复盘日期不能晚于今天")
    if requested == local_now.date():
        effective = await get_completed_market_date(requested, now=local_now)
    else:
        effective = await get_market_date_on_or_before(requested)
    return DailyReviewDateResolution(
        requested_date=requested,
        effective_date=effective,
        session_status="completed" if effective == requested else "adjusted",
        use_realtime=effective == local_now.date(),
    )


def _build_prompt(
    date_text: str,
    snapshot: DailyReviewDataSnapshot,
    *,
    previous_review_check: DailyReviewPreviousCheck | None = None,
    cycle_trend: CycleTrend | None = None,
) -> str:
    return cast(str, review_builder.build_prompt(
        date_text,
        snapshot,
        MARKET_USER_PROMPT,
        previous_review_check=previous_review_check,
        cycle_trend=cycle_trend,
    ))


def _snapshot_limit_up_count(snapshot: DailyReviewDataSnapshot) -> int | None:
    statistics = snapshot.market_statistics or {}
    value = statistics.get("limit_up_count")
    return value if isinstance(value, int) else None


async def _review_history_inputs(
    effective_text: str,
    resolution: DailyReviewDateResolution,
    snapshot: DailyReviewDataSnapshot,
) -> tuple[DailyReviewPreviousCheck | None, CycleTrend]:
    """读取按日期存放的全局周期摘要：上一交易日自检 + 情绪周期历史趋势。"""

    def _load() -> tuple[DailyReviewCycleRecord | None, list[DailyReviewCycleRecord]]:
        return previous_cycle_record(effective_text), recent_cycle_records(
            _CYCLE_TREND_DAYS,
            before=effective_text,
        )

    try:
        previous, records = await call_blocking(_load, semaphore=misc_semaphore)
    except Exception:  # noqa: BLE001 - 历史摘要缺失不应阻断复盘生成
        logger.warning("复盘周期摘要读取失败，跳过自检与趋势: date=%s", effective_text, exc_info=True)
        return None, CycleTrend(note="历史摘要读取失败")
    check = await build_previous_review_check(
        previous,
        verified_date=resolution.effective_date,
        current_indices=snapshot.indices,
        current_limit_up_count=_snapshot_limit_up_count(snapshot),
    )
    return check, build_cycle_trend(records, days=_CYCLE_TREND_DAYS)


async def _save_cycle_record(
    *,
    date_text: str,
    snapshot: DailyReviewDataSnapshot,
    sentiment_cycle: DailyReviewSentimentCycle | None,
    watchlist: list[DailyReviewWatchItem],
    key_levels: list[str],
) -> None:
    record = build_cycle_record(
        date_text=date_text,
        snapshot=snapshot,
        sentiment_cycle=sentiment_cycle,
        watchlist=watchlist,
        key_levels=key_levels,
    )
    try:
        await call_blocking(save_cycle_record, record, semaphore=misc_semaphore)
    except Exception:  # noqa: BLE001 - 摘要写入失败不应影响复盘返回
        logger.warning("复盘周期摘要写入失败: date=%s", date_text, exc_info=True)


def _build_snapshot(
    values: dict,
    *,
    requested_date: str,
    effective_date: str,
    source_status: dict,
    policy_news: list,
) -> DailyReviewDataSnapshot:
    return cast(DailyReviewDataSnapshot, review_builder.build_snapshot(
        values.get("indices"),
        values.get("hot_stocks"),
        values.get("hot_concepts"),
        values.get("hot_industries"),
        values.get("dragon_tiger"),
        values.get("market_statistics"),
        values.get("market_news"),
        values.get("market_volume"),
        values.get("macro_data"),
        macro_analysis=values.get("macro_analysis"),
        policy_news=policy_news,
        limit_up_ladder=values.get("limit_up_ladder"),
        limit_break_pool=values.get("limit_break_pool"),
        northbound_funds=values.get("northbound_funds"),
        requested_date=requested_date,
        effective_date=effective_date,
        source_status=source_status,
    ))


# 核心数据源缺失才判定整体降级；热点榜/宏观等辅助数据缺失只记录说明。
_CORE_REVIEW_SOURCES = ("indices", "market_statistics", "market_volume", "market_news")


def _quality(
    snapshot: DailyReviewDataSnapshot,
) -> tuple[Literal["complete", "degraded"], list[str], list[str], dict[str, str]]:
    errors = {
        name: status.error
        for name, status in snapshot.source_status.items()
        if status.status == "unavailable" and status.error
    }
    warnings = [
        f"{name}：{error}"
        for name, error in errors.items()
        if name in _CORE_REVIEW_SOURCES
    ]
    notes = [
        f"{name}：{error}"
        for name, error in errors.items()
        if name not in _CORE_REVIEW_SOURCES
    ]
    notes.extend(
        f"{name}：数据部分可用"
        for name, status in snapshot.source_status.items()
        if status.status == "partial"
    )
    core_missing = [
        name
        for name in _CORE_REVIEW_SOURCES
        if snapshot.source_status.get(name) is None
        or snapshot.source_status[name].status == "unavailable"
    ]
    if core_missing:
        warnings.insert(0, f"核心复盘数据缺失：{'、'.join(core_missing)}")
    return ("degraded" if warnings else "complete"), warnings, notes, errors


async def generate_daily_review(
    request: DailyReviewRequest,
    user_id: int,
    progress_callback: DailyReviewProgressCallback | None = None,
) -> DailyReviewResult:
    """Generate a date-consistent daily review with explicit source quality."""
    progress = ProgressEmitter(progress_callback)
    resolution = await resolve_daily_review_date(request.date)
    await progress.emit({"type": "stage_started", "stage": "queue", "message": _QUEUE_MESSAGE})
    lock = await _generation_lock((resolution.effective_date.isoformat(), user_id))
    async with lock:
        await _stage_completed(progress, "queue", "已获得生成锁，开始采集数据")
        return await _generate_daily_review_locked(request, user_id, resolution, progress)


async def _generate_daily_review_locked(
    request: DailyReviewRequest,
    user_id: int,
    resolution: DailyReviewDateResolution,
    progress: ProgressEmitter[dict[str, Any]],
) -> DailyReviewResult:
    requested_text = resolution.requested_date.isoformat()
    effective_text = resolution.effective_date.isoformat()
    if not request.force:
        cached = await call_blocking(
            load_daily_review,
            effective_text,
            user_id,
            semaphore=misc_semaphore,
        )
        if cached is not None:
            cached_review = cached if isinstance(cached, DailyReviewResult) else DailyReviewResult.model_validate(cached)
            if not await _cached_review_staleness(cached_review):
                await progress.emit({
                    "type": "cache_hit",
                    "stage": "queue",
                    "message": f"复用 {effective_text} 已有复盘，未重新生成",
                })
                return cast(DailyReviewResult, cached_review.model_copy(update={"requested_date": requested_text}))
            logger.info("缓存复盘已过期，自动重新采集: date=%s", effective_text)

    await _stage_started(progress, "collect", _COLLECT_MESSAGE)
    collection = await _collect_shared(resolution, progress)
    await _stage_completed(
        progress, "collect", "数据采集完成",
        sources=len(collection.source_status),
        failed=sum(1 for status in collection.source_status.values() if status.status == "unavailable"),
    )
    snapshot = _build_snapshot(
        collection.values,
        requested_date=requested_text,
        effective_date=effective_text,
        source_status=collection.source_status,
        policy_news=collection.policy_news,
    )
    previous_check, cycle_trend = await _review_history_inputs(effective_text, resolution, snapshot)
    quality_status, warnings, notes, source_errors = _quality(snapshot)

    await _stage_started(progress, "analyze", _ANALYZE_MESSAGE)
    settings = get_effective_settings()
    user_content = _build_prompt(
        effective_text,
        snapshot,
        previous_review_check=previous_check,
        cycle_trend=cycle_trend,
    )
    review = cast(DailyReviewResult, review_builder.build_fallback_review(
        effective_text,
        snapshot,
        generated_at=_local_now().isoformat(timespec="seconds"),
    ))
    generation_status: Literal["llm", "fallback"] = "fallback"
    llm_error = ""
    try:
        # 强制刷新时跳过共享输出缓存，保证「重新生成」确实重新调用模型。
        await progress.emit({
            "type": "stage_progress", "stage": "analyze",
            "message": f"提示词已构建（{len(user_content)} 字符），正在调用模型",
        })
        async with _stage_heartbeat(progress, "analyze", "正在生成 AI 复盘报告"):
            prompt_run = await _run_review_prompt(user_content, settings, allow_cache=not request.force)
        output = prompt_run.value
        generation_status = "llm"
        review.market_state = output.market_state
        review.market_summary = output.market_summary
        review.index_review = output.index_review
        review.hotspot_review = output.hotspot_review
        review.dragon_tiger_review = output.dragon_tiger_review
        review.news_policy_review = review_builder.ground_news_policy_section(
            snapshot,
            output.news_policy_review,
        )
        review.event_impacts = review_builder.ground_event_impacts(snapshot, output.event_impacts)
        review.risk_alerts = output.risk_alerts
        review.opportunities = output.opportunities
        review.strategy_notes = output.strategy_notes
        review.sentiment_cycle = output.sentiment_cycle
        review.scenario_plans = output.scenario_plans
        # 次日观察标的必须是快照里真实存在的个股，否则视为虚构。
        review.next_day_watchlist = review_builder.ground_watchlist(snapshot, output.next_day_watchlist)
        review.key_levels = output.key_levels
        await progress.emit({
            "type": "stage_progress", "stage": "analyze",
            "message": "模型输出已就绪，正在做确定性校验与兜底",
        })
        review.position_range = output.position_range
        review.invalid_conditions = output.invalid_conditions
        review.data_gaps = output.data_gaps
        review.prompt_trace = prompt_run.trace
    except Exception as error:
        quality_status = "degraded"
        llm_error = str(error) or type(error).__name__
        warnings.append(f"AI 复盘生成失败，已使用确定性兜底：{llm_error}")
        if isinstance(error, PromptExecutionError):
            review.prompt_trace = error.trace
        if isinstance(error, LLMConfigurationError):
            logger.warning("结构化复盘未调用 LLM，配置不可用: date=%s error=%s", effective_text, error)
        else:
            logger.warning("结构化复盘生成失败，使用确定性兜底: date=%s", effective_text, exc_info=True)

    review.requested_date = requested_text
    review.effective_date = effective_text
    review.session_status = resolution.session_status
    review.quality_status = quality_status
    review.generation_status = generation_status
    review.warnings = warnings
    review.notes = notes
    review.source_errors = source_errors
    review.llm_error = llm_error
    review.previous_review_check = previous_check
    review.cycle_trend = cycle_trend
    review.llm_review = render_daily_review_markdown(review)
    await _stage_completed(progress, "analyze", "AI 复盘生成完成", generation_status=generation_status)
    await _stage_started(progress, "persist", _PERSIST_MESSAGE)
    await call_blocking(
        save_daily_review,
        review,
        user_id,
        semaphore=misc_semaphore,
    )
    # 写全局按日摘要：供次日自检与情绪周期趋势使用。
    await _save_cycle_record(
        date_text=effective_text,
        snapshot=snapshot,
        sentiment_cycle=review.sentiment_cycle,
        watchlist=review.next_day_watchlist,
        key_levels=review.key_levels,
    )
    await _stage_completed(progress, "persist", "复盘已保存")
    try:
        from app.core.events import event_bus
        await event_bus.publish(review, name="daily_review.completed")
    except Exception:  # noqa: BLE001 - 事件发布异常绝不阻断复盘返回
        logger.warning("发布每日复盘完成事件失败: date=%s", effective_text, exc_info=True)
    return review


async def prewarm_daily_review(date_text: str | None = None) -> bool:
    """收盘后预热当日复盘：采集快照并生成一次 AI 输出写入共享缓存，不落库。

    返回 True 表示本次确实调用了模型；缓存已就绪或不是当日收盘口径时返回 False。
    """
    requested: date | None = None
    if date_text:
        try:
            requested = date.fromisoformat(date_text)
        except ValueError:
            logger.warning("每日复盘预热日期无效: %s", date_text)
            return False
    try:
        resolution = await resolve_daily_review_date(requested)
    except ValueError:
        logger.warning("每日复盘预热日期不可用: %s", date_text or "今天")
        return False
    if not resolution.use_realtime:
        # 只有当日行情已收盘定型（use_realtime）才预热；其余时段用户拿到的是最近交易日复盘。
        return False

    effective_text = resolution.effective_date.isoformat()
    collection = await _collect_shared(resolution)
    snapshot = _build_snapshot(
        collection.values,
        requested_date=resolution.requested_date.isoformat(),
        effective_date=effective_text,
        source_status=collection.source_status,
        policy_news=collection.policy_news,
    )
    previous_check, cycle_trend = await _review_history_inputs(effective_text, resolution, snapshot)
    settings = get_effective_settings()
    user_content = _build_prompt(
        effective_text,
        snapshot,
        previous_review_check=previous_check,
        cycle_trend=cycle_trend,
    )
    if analysis_cache.get(_review_llm_cache_key(user_content)) is not None:
        return False
    try:
        prompt_run = await _run_review_prompt(user_content, settings, allow_cache=True)
    except Exception as error:  # noqa: BLE001 - 后台任务不应因单次预热失败而退出
        logger.warning("每日复盘后台预热失败: date=%s error=%s", effective_text, error)
        return False
    # 预热时同样写全局摘要：让趋势与自检不依赖任何用户是否生成过复盘。
    await _save_cycle_record(
        date_text=effective_text,
        snapshot=snapshot,
        sentiment_cycle=prompt_run.value.sentiment_cycle,
        watchlist=review_builder.ground_watchlist(snapshot, prompt_run.value.next_day_watchlist),
        key_levels=prompt_run.value.key_levels,
    )
    logger.info("每日复盘预热完成: date=%s", effective_text)
    return True
