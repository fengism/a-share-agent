"""具体后台任务定义。"""

import logging

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.runtime import task_scheduler

logger = logging.getLogger(__name__)


async def refresh_industry_mapping_file_daily() -> None:
    """定期（默认每周）自动更新申万行业分类并联动同步官方股票名录。"""
    from app.modules.industry_classification.public import scheduled_refresh
    from app.modules.stock_profile.public import (
        auto_enrich_pending_profiles,
        sync_exchange_master_data,
    )

    async def iteration():
        # 1. 尝试按配置周期（默认每周）更新申万行业
        result = await scheduled_refresh()
        if result is not None:
            logger.info(
                "申万行业数据库周期更新完成: added=%s updated=%s unchanged=%s",
                result.added,
                result.updated,
                result.unchanged,
            )
            # 2. 行业更新成功后，联动同步官方交易所股票名录，自动绑定最新申万行业
            try:
                sync_res = await sync_exchange_master_data()
                logger.info(
                    "交易所股票名录联动周更完成: added=%s updated=%s unchanged=%s skipped=%s",
                    sync_res.added,
                    sync_res.updated,
                    sync_res.unchanged,
                    sync_res.skipped,
                )
            except Exception as e:
                logger.warning("交易所股票名录联动更新失败，保留当前资料: %s", e)

        # 3. 后台平滑跑批：每次为缺失主营资料的股票补充 50 只（使用同花顺/东财公开源，免 Token）
        try:
            enrich_stats = await auto_enrich_pending_profiles(batch_size=50, delay_seconds=0.5)
            if enrich_stats["enriched"] > 0:
                logger.info(
                    "后台个股主营资料补充进度: enriched=%s processed=%s remaining=%s",
                    enrich_stats["enriched"],
                    enrich_stats["processed"],
                    enrich_stats["remaining"],
                )
        except Exception as e:
            logger.debug("后台自动补充主营资料跳过: %s", e)

        # 4. 后台平滑跑批：每次为缺失概念的股票补充同花顺概念（免 Token 公开源）
        try:
            from app.modules.stock_concept.public import auto_enrich_pending_concepts
            concept_stats = await auto_enrich_pending_concepts(batch_size=20, delay_seconds=0.5)
            if concept_stats["enriched"] > 0:
                logger.info(
                    "后台个股概念补充进度: enriched=%s processed=%s remaining=%s",
                    concept_stats["enriched"],
                    concept_stats["processed"],
                    concept_stats["remaining"],
                )
        except Exception as e:
            logger.debug("后台自动补充个股概念跳过: %s", e)

    await task_scheduler.run_periodic(
        name="industry_mapping_refresh",
        coro_factory=iteration,
        interval_seconds=60 * 60,  # 每小时检查一次（行业按7天周更，未录入主营按批平滑补充）
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
        from app.modules.market_daily.service import market_daily_bar_service

        market_daily_maintained = await market_daily_bar_service.maintain_storage(
            observation_retention_days=settings.market_daily_observation_retention_days,
            attempt_retention_days=settings.market_daily_attempt_retention_days,
        )
        optimized = await call_blocking(optimize_databases, semaphore=database_semaphore)
        checkpointed = await call_blocking(checkpoint_wal, semaphore=database_semaphore)
        logger.info(
            "SQLite 周期维护完成: auth=%s runtime=%s market_daily=%s optimize=%s checkpoint=%s",
            auth_purged,
            runtime_purged,
            market_daily_maintained,
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
    from app.infrastructure.persistence.connection import default_backup_dir
    from app.infrastructure.persistence.operations import (
        STARTUP_CRITICAL_DATABASES,
        backup_databases_due,
        create_online_backups,
    )

    async def iteration():
        settings = get_settings()
        if not settings.database_backup_enabled:
            return
        backup_dir = settings.database_backup_dir or default_backup_dir()

        due_critical = set(await call_blocking(
            backup_databases_due,
            backup_dir,
            interval_seconds=settings.database_backup_interval_seconds,
            databases=STARTUP_CRITICAL_DATABASES,
            semaphore=database_semaphore,
        ))
        if settings.database_backup_mirror_dir is not None:
            due_critical.update(await call_blocking(
                backup_databases_due,
                settings.database_backup_mirror_dir,
                interval_seconds=settings.database_backup_interval_seconds,
                databases=STARTUP_CRITICAL_DATABASES,
                semaphore=database_semaphore,
            ))

        due_market_daily = False
        if getattr(settings, "database_backup_include_market_daily", True):
            market_daily_interval = max(3600, int(settings.market_daily_backup_interval_days * 86400))
            market_daily_due = set(await call_blocking(
                backup_databases_due,
                backup_dir,
                interval_seconds=market_daily_interval,
                databases=("market_daily",),
                semaphore=database_semaphore,
            ))
            if settings.database_backup_mirror_dir is not None:
                market_daily_due.update(await call_blocking(
                    backup_databases_due,
                    settings.database_backup_mirror_dir,
                    interval_seconds=market_daily_interval,
                    databases=("market_daily",),
                    semaphore=database_semaphore,
                ))
            due_market_daily = bool(market_daily_due)

        if not due_critical and not due_market_daily:
            logger.debug("SQLite 在线备份未到期，跳过本轮")
            return

        created = []
        if due_critical:
            created_critical = await call_blocking(
                create_online_backups,
                backup_dir,
                retention_count=settings.database_backup_retention_count,
                databases=tuple(database for database in STARTUP_CRITICAL_DATABASES if database in due_critical),
                mirror_dir=settings.database_backup_mirror_dir,
                semaphore=database_semaphore,
            )
            created.extend(created_critical)

        if due_market_daily:
            created_market_daily = await call_blocking(
                create_online_backups,
                backup_dir,
                retention_count=settings.database_backup_retention_count,
                databases=("market_daily",),
                mirror_dir=settings.database_backup_mirror_dir,
                compression_level=settings.market_daily_backup_compression_level,
                semaphore=database_semaphore,
            )
            created.extend(created_market_daily)

        logger.info("SQLite 在线备份完成: files=%s", [str(path) for path in created])

    settings = get_settings()
    await task_scheduler.run_periodic(
        name="database_backup",
        coro_factory=iteration,
        interval_seconds=min(settings.database_backup_interval_seconds, 3600),
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

    cursor = get_connection().execute("SELECT 1")
    cursor.fetchone()
    cursor.close()


async def twitter_health_check() -> bool:
    try:
        await call_blocking(
            _check_twitter_database,
            semaphore=database_semaphore,
        )
        return True
    except Exception:
        return False


async def refresh_market_daily_bars_periodic() -> None:
    """盘后归档独立历史日线；实时行情由实时查询链负责，不写入此库。"""
    from app.modules.market_daily.service import market_daily_bar_service

    service = market_daily_bar_service
    await service.initialize()

    async def iteration():
        await service.run_scheduled()

    await task_scheduler.run_periodic(
        name="market_daily_bar_refresh",
        coro_factory=iteration,
        interval_seconds=15,
        leader_election=True,
        retry_base_seconds=15,
    )


async def refresh_potential_stocks_daily() -> None:
    """仅在交易日收盘后自动挖掘潜力股。"""
    from app.modules.potential.public import run_scheduled_daily_mining

    async def iteration():
        await run_scheduled_daily_mining()

    await task_scheduler.run_periodic(
        name="potential_stock_daily",
        coro_factory=iteration,
        interval_seconds=1800,
        leader_election=True,
    )



async def run_market_daily_backfill_worker() -> None:
    """执行管理员提交的 A 股全市场历史日线回填任务。"""
    from app.modules.market_daily.backfill import market_daily_backfill_service

    await market_daily_backfill_service.run_worker()
