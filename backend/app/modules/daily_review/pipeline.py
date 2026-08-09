import asyncio
import logging
import time
from datetime import datetime

from app.configuration import get_effective_settings
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.retry import RetryPolicy
from app.infrastructure.llm.sync_client import llm_chat
from app.market_data.market.public import (
    get_dragon_tiger_list,
    get_hot_stocks,
    get_indices,
    get_macro_data,
    get_market_news,
    get_market_statistics,
    get_realtime_market_volume,
    get_ths_hot_concept,
    get_ths_hot_industry,
)
from app.modules.daily_review import review_builder
from app.modules.daily_review.formatter import normalize_llm_review
from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult
from app.modules.daily_review.persistence.repository import load_daily_review, save_daily_review
from app.modules.daily_review.prompts import MARKET_SYSTEM_PROMPT, MARKET_USER_PROMPT
from app.modules.daily_review.schemas import DailyReviewRequest

logger = logging.getLogger(__name__)

_LLM_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay_seconds=2.0,
    max_elapsed_seconds=15.0,
    jitter_seconds=0.25,
)


def _build_fallback_review(date: str, snapshot: DailyReviewDataSnapshot) -> DailyReviewResult:
    return review_builder.build_fallback_review(
        date,
        snapshot,
        generated_at=datetime.now().isoformat(),
    )


def _build_prompt(date: str, snapshot: DailyReviewDataSnapshot) -> str:
    return review_builder.build_prompt(date, snapshot, MARKET_USER_PROMPT)


def _build_snapshot(
    indices,
    hot_stocks,
    hot_concepts,
    hot_industries,
    dragon_tiger,
    market_statistics,
    market_news,
    market_volume,
    macro_data,
) -> DailyReviewDataSnapshot:
    return review_builder.build_snapshot(
        indices,
        hot_stocks,
        hot_concepts,
        hot_industries,
        dragon_tiger,
        market_statistics,
        market_news,
        market_volume,
        macro_data,
    )


async def generate_daily_review(request: DailyReviewRequest, user_id: int) -> DailyReviewResult:
    """生成每日复盘报告：优先读取缓存，否则并行采集数据并调用 LLM 生成分析。"""
    date = request.date or datetime.now().strftime("%Y-%m-%d")
    if not request.force:
        cached = await call_blocking(
            load_daily_review,
            date,
            user_id,
            semaphore=misc_semaphore,
        )
        if cached is not None:
            return cached

    (
        indices,
        hot_stocks,
        hot_concepts,
        hot_industries,
        dragon_tiger,
        market_statistics,
        market_news,
        market_volume,
        macro_data,
    ) = await asyncio.gather(
        get_indices(),
        get_hot_stocks(),
        get_ths_hot_concept(),
        get_ths_hot_industry(),
        get_dragon_tiger_list(date),
        get_market_statistics(date),
        get_market_news(),
        get_realtime_market_volume(),
        get_macro_data(),
        return_exceptions=True,
    )

    snapshot = _build_snapshot(
        indices=indices,
        hot_stocks=hot_stocks,
        hot_concepts=hot_concepts,
        hot_industries=hot_industries,
        dragon_tiger=dragon_tiger,
        market_statistics=market_statistics,
        market_news=market_news,
        market_volume=market_volume,
        macro_data=macro_data,
    )
    llm_review = ""
    last_error: Exception | None = None
    settings = get_effective_settings()
    user_content = _build_prompt(date, snapshot)
    started_at = time.monotonic()
    for attempt in range(1, _LLM_RETRY_POLICY.max_attempts + 1):
        try:
            logger.info(
                "生成复盘报告: date=%s, prompt_length=%s, attempt=%s/%s",
                date,
                len(user_content),
                attempt,
                _LLM_RETRY_POLICY.max_attempts,
            )
            llm_review = normalize_llm_review(
                (
                    await llm_chat(
                        [
                            {"role": "system", "content": MARKET_SYSTEM_PROMPT},
                            {"role": "user", "content": user_content},
                        ],
                        temperature=settings.llm_temperature,
                    )
                ).strip()
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "生成复盘报告失败 (attempt %s/%s): date=%s",
                attempt,
                _LLM_RETRY_POLICY.max_attempts,
                date,
                exc_info=True,
            )
            delay = _LLM_RETRY_POLICY.delay_seconds(attempt)
            if not _LLM_RETRY_POLICY.can_retry(
                attempt_number=attempt,
                elapsed_seconds=time.monotonic() - started_at,
                delay_seconds=delay,
            ):
                break
            await asyncio.sleep(delay)
    if last_error is not None and not llm_review:
        logger.error(
            "生成复盘报告失败: date=%s attempts=%s error_type=%s",
            date,
            attempt,
            type(last_error).__name__,
        )

    review = _build_fallback_review(date, snapshot)
    review.llm_review = llm_review
    await call_blocking(
        save_daily_review,
        review,
        user_id,
        semaphore=misc_semaphore,
    )
    return review
