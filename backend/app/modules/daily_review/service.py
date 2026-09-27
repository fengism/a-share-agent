"""每日复盘生成与历史记录应用服务。"""

import logging
from datetime import date as dt_date

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.financial_data.market.public import get_market_volume_stats
from app.modules.daily_review import pipeline
from app.modules.daily_review.models import DailyReviewResult
from app.modules.daily_review.persistence import repository
from app.modules.daily_review.schemas import DailyReviewRequest

logger = logging.getLogger(__name__)


async def generate_daily_review(request: DailyReviewRequest, user_id: int) -> DailyReviewResult:
    return await pipeline.generate_daily_review(request, user_id)


def load_daily_review(date: str, user_id: int) -> DailyReviewResult | None:
    """同步读取复盘记录，供同步业务流程复用。"""
    return repository.load_daily_review(date, user_id)


async def get_daily_review_record(date: str, user_id: int) -> DailyReviewResult | None:
    record = await call_blocking(
        repository.load_daily_review,
        date,
        user_id,
        semaphore=misc_semaphore,
    )
    if record is not None:
        record = await _backfill_market_volume_stats(record, user_id)
    return record


async def _backfill_market_volume_stats(record: DailyReviewResult, user_id: int) -> DailyReviewResult:
    """为缺少均线维度的旧版复盘快照回填成交额统计，成功后写回持久化避免每次查看重复拉取。"""
    snapshot = record.data_snapshot
    if snapshot is None or not snapshot.market_volume:
        return record
    mv = snapshot.market_volume
    if not mv.get("amount") or (
        mv.get("amount_before_one_day") is not None
        and mv.get("amount_average_20_day") is not None
        and mv.get("amount_average_60_day") is not None
    ):
        return record
    try:
        target_dt = dt_date.fromisoformat(record.effective_date or record.date)
        stats = await get_market_volume_stats(target_dt, use_realtime=False)
    except Exception as error:
        logger.warning("复盘 %s 成交额均线回填失败: %s", record.date, error)
        return record
    if not stats.amount:
        return record
    if mv.get("amount_before_one_day") is None and stats.amount_before_one_day is not None:
        mv["amount_before_one_day"] = stats.amount_before_one_day
    if mv.get("amount_average_20_day") is None and stats.amount_average_20_day is not None:
        mv["amount_average_20_day"] = stats.amount_average_20_day
    if mv.get("amount_average_60_day") is None and stats.amount_average_60_day is not None:
        mv["amount_average_60_day"] = stats.amount_average_60_day
    try:
        await call_blocking(
            repository.save_daily_review,
            record,
            user_id,
            semaphore=misc_semaphore,
        )
    except Exception as error:
        logger.warning("复盘 %s 回填结果写回失败: %s", record.date, error)
    return record


async def list_daily_review_history(
    user_id: int,
    *,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
) -> list[dict]:
    return await call_blocking(
        repository.list_daily_reviews,
        user_id,
        limit,
        offset,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )


async def remove_daily_review(date: str, user_id: int, *, can_delete_legacy: bool) -> bool:
    return await call_blocking(
        repository.delete_daily_review,
        date,
        user_id,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )
