"""具体后台任务定义。"""

import logging

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.runtime import task_scheduler

logger = logging.getLogger(__name__)


async def refresh_industry_mapping_file_daily() -> None:
    from app.market_data.stock.public import update_industry_mapping_sw_second_file

    async def iteration():
        await call_blocking(update_industry_mapping_sw_second_file)
        logger.info("行业映射文件更新完成")

    await task_scheduler.run_periodic(
        name="industry_mapping_refresh",
        coro_factory=iteration,
        interval_seconds=24 * 60 * 60,
        leader_election=True,
    )


async def periodic_wal_checkpoint() -> None:
    from app.infrastructure.persistence.connection import checkpoint_wal
    from app.infrastructure.persistence.session_store import purge_expired
    from app.runtime.maintenance import purge_expired_runtime_data

    async def iteration():
        settings = get_settings()
        runtime_purged = await call_blocking(
            purge_expired_runtime_data,
            bot_job_retention_seconds=settings.bot_event_dedup_ttl_seconds,
            bot_rate_limit_window_seconds=settings.bot_rate_limit_window,
            twitter_post_retention_days=settings.twitter_post_retention_days,
            semaphore=database_semaphore,
        )
        await call_blocking(checkpoint_wal, semaphore=database_semaphore)
        auth_purged = await call_blocking(purge_expired, semaphore=database_semaphore)
        logger.info(
            "WAL checkpoint 完成，过期数据已清理: auth=%s runtime=%s",
            auth_purged,
            runtime_purged,
        )

    await task_scheduler.run_periodic(
        name="wal_checkpoint",
        coro_factory=iteration,
        interval_seconds=6 * 60 * 60,
        leader_election=True,
    )


async def refresh_twitter_feed_periodic() -> None:
    from app.infrastructure.persistence.twitter_store import TWITTER_REFRESH_INTERVAL_SECONDS, get_stale_authors
    from app.market_data.market.public import refresh_twitter_feeds

    async def iteration():
        feeds = get_settings().twitter_feeds
        if not feeds:
            return
        stale = await call_blocking(
            get_stale_authors,
            feeds,
            semaphore=database_semaphore,
        )
        if not stale:
            logger.debug("Twitter no refresh needed: %s", feeds)
            return
        logger.info("Twitter fetching stale authors: %s", stale)
        await refresh_twitter_feeds(stale)

    await task_scheduler.run_periodic(
        name="twitter_feed",
        coro_factory=iteration,
        interval_seconds=TWITTER_REFRESH_INTERVAL_SECONDS,
        health_check=twitter_health_check,
        leader_election=True,
    )


def _check_twitter_database() -> None:
    from app.infrastructure.persistence.connection import get_connection

    get_connection().execute("SELECT 1")


async def twitter_health_check() -> bool:
    try:
        await call_blocking(
            _check_twitter_database,
            semaphore=database_semaphore,
        )
        return True
    except Exception:
        return False
