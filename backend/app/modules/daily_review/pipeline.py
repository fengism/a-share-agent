import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, cast
from zoneinfo import ZoneInfo

from app.configuration import get_effective_settings
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.domain.llm import LLMConfigurationError
from app.financial_data.market.public import get_completed_market_date, get_market_date_on_or_before
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
from app.modules.daily_review import review_builder
from app.modules.daily_review.collector import collect_daily_review_data
from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult
from app.modules.daily_review.persistence.repository import load_daily_review, save_daily_review
from app.modules.daily_review.prompts import DAILY_REVIEW_PROMPT_SPEC, MARKET_USER_PROMPT
from app.modules.daily_review.report_renderer import render_daily_review_markdown
from app.modules.daily_review.schemas import DailyReviewRequest

logger = logging.getLogger(__name__)
_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _cached_review_needs_news_refresh(review: DailyReviewResult) -> bool:
    if review.schema_version < 5:
        return True
    effective_date = review.effective_date or review.data_snapshot.effective_date or review.date
    if effective_date == "2026-09-29":
        housing_policy_text = " ".join(
            f"{item.title} {item.content}"
            for item in review.data_snapshot.policy_news
        )
        if "贴息" not in housing_policy_text or not any(
            keyword in housing_policy_text
            for keyword in ("购房", "房贷", "住房贷款", "按揭")
        ):
            # 早期 v4 复盘可能只有泛财经新闻，尚未启用房地产/购房贴息专项搜索。
            # 9 月 29 日是已确认的中央购房贷款贴息政策发布日期，无该事件则自动补采一次。
            return True
    status = review.data_snapshot.source_status.get("market_news")
    if status is None:
        return review.schema_version < 4
    return status.status == "unavailable" and (
        "有效发布时间" in status.error
        or "复盘时点附近" in status.error
        or "未使用当前新闻替代" in status.error
        or "Web Search 财经政策新闻" in status.error
    )


@dataclass(frozen=True)
class DailyReviewDateResolution:
    requested_date: date
    effective_date: date
    session_status: Literal["completed", "adjusted"]
    use_realtime: bool


def _local_now() -> datetime:
    return datetime.now(_MARKET_TIMEZONE)


async def resolve_daily_review_date(
    requested_date: date | None,
    *,
    now: datetime | None = None,
) -> DailyReviewDateResolution:
    local_now = (now or _local_now()).astimezone(_MARKET_TIMEZONE)
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


def _build_prompt(date_text: str, snapshot: DailyReviewDataSnapshot) -> str:
    return cast(str, review_builder.build_prompt(date_text, snapshot, MARKET_USER_PROMPT))


def _build_snapshot(
    values: dict,
    *,
    requested_date: str,
    effective_date: str,
    source_status: dict,
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
        limit_up_ladder=values.get("limit_up_ladder"),
        northbound_funds=values.get("northbound_funds"),
        requested_date=requested_date,
        effective_date=effective_date,
        source_status=source_status,
    ))


def _quality(
    snapshot: DailyReviewDataSnapshot,
) -> tuple[Literal["complete", "degraded"], list[str], dict[str, str]]:
    errors = {
        name: status.error
        for name, status in snapshot.source_status.items()
        if status.status == "unavailable" and status.error
    }
    partial = [name for name, status in snapshot.source_status.items() if status.status == "partial"]
    warnings = [f"{name}：{error}" for name, error in errors.items()]
    warnings.extend(f"{name}：数据部分可用" for name in partial)
    core_missing = [
        name
        for name in ("indices", "market_statistics", "market_volume")
        if snapshot.source_status.get(name) is None
        or snapshot.source_status[name].status == "unavailable"
    ]
    if core_missing:
        warnings.insert(0, f"核心复盘数据缺失：{'、'.join(core_missing)}")
    return ("degraded" if warnings else "complete"), warnings, errors


async def generate_daily_review(request: DailyReviewRequest, user_id: int) -> DailyReviewResult:
    """Generate a date-consistent daily review with explicit source quality."""
    resolution = await resolve_daily_review_date(request.date)
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
            if not _cached_review_needs_news_refresh(cached_review):
                return cast(DailyReviewResult, cached_review.model_copy(update={"requested_date": requested_text}))
            logger.info("旧复盘新闻时间不可用，自动重新采集: date=%s", effective_text)

    collection = await collect_daily_review_data(
        resolution.effective_date,
        use_realtime=resolution.use_realtime,
    )
    snapshot = _build_snapshot(
        collection.values,
        requested_date=requested_text,
        effective_date=effective_text,
        source_status=collection.source_status,
    )
    quality_status, warnings, source_errors = _quality(snapshot)

    settings = get_effective_settings()
    user_content = _build_prompt(effective_text, snapshot)
    review = cast(DailyReviewResult, review_builder.build_fallback_review(
        effective_text,
        snapshot,
        generated_at=_local_now().isoformat(timespec="seconds"),
    ))
    generation_status: Literal["llm", "fallback"] = "fallback"
    llm_error = ""
    try:
        prompt_run = await run_structured_prompt(
            DAILY_REVIEW_PROMPT_SPEC,
            {"prompt": user_content},
            settings=settings,
            max_tokens=settings.analysis_llm_max_completion_tokens,
            timeout_seconds=settings.analysis_llm_timeout_seconds,
        )
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
    review.source_errors = source_errors
    review.llm_error = llm_error
    review.llm_review = render_daily_review_markdown(review)
    await call_blocking(
        save_daily_review,
        review,
        user_id,
        semaphore=misc_semaphore,
    )
    return review
