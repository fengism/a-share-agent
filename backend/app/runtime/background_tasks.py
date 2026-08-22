"""具体后台任务定义。"""

import logging

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.runtime import task_scheduler

logger = logging.getLogger(__name__)


async def refresh_industry_mapping_file_daily() -> None:
    from app.financial_data.stock.public import update_industry_mapping_sw_second_file

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
    from app.infrastructure.persistence.connection import checkpoint_wal, optimize_databases
    from app.runtime.maintenance import purge_expired_auth_data, purge_expired_runtime_data

    async def iteration():
        settings = get_settings()
        runtime_purged = await call_blocking(
            purge_expired_runtime_data,
            bot_job_retention_seconds=settings.bot_event_dedup_ttl_seconds,
            bot_rate_limit_window_seconds=settings.bot_rate_limit_window,
            twitter_post_retention_days=settings.twitter_post_retention_days,
            workflow_job_retention_seconds=settings.workflow_job_retention_seconds,
            semaphore=database_semaphore,
        )
        auth_purged = await call_blocking(purge_expired_auth_data, semaphore=database_semaphore)
        optimized = await call_blocking(optimize_databases, semaphore=database_semaphore)
        checkpointed = await call_blocking(checkpoint_wal, semaphore=database_semaphore)
        logger.info(
            "SQLite 周期维护完成: auth=%s runtime=%s optimize=%s checkpoint=%s",
            auth_purged,
            runtime_purged,
            optimized,
            checkpointed,
        )

    await task_scheduler.run_periodic(
        name="wal_checkpoint",
        coro_factory=iteration,
        interval_seconds=6 * 60 * 60,
        leader_election=True,
    )


async def periodic_database_backup() -> None:
    from app.infrastructure.persistence.operations import create_online_backups

    async def iteration():
        settings = get_settings()
        if not settings.database_backup_enabled:
            return
        created = await call_blocking(
            create_online_backups,
            settings.database_backup_dir or settings.app_data_dir / "backups",
            retention_count=settings.database_backup_retention_count,
            mirror_dir=settings.database_backup_mirror_dir,
            semaphore=database_semaphore,
        )
        logger.info("SQLite 在线备份完成: files=%s", [str(path) for path in created])

    settings = get_settings()
    await task_scheduler.run_periodic(
        name="database_backup",
        coro_factory=iteration,
        interval_seconds=settings.database_backup_interval_seconds,
        leader_election=True,
    )


async def refresh_twitter_feed_periodic() -> None:
    from app.financial_data.market.public import refresh_twitter_feeds
    from app.infrastructure.persistence.twitter_store import TWITTER_REFRESH_INTERVAL_SECONDS, get_stale_authors

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
