"""具体后台任务定义。"""

import logging
from pathlib import Path
from typing import cast

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, tdxhub_semaphore
from app.runtime import task_scheduler

logger = logging.getLogger(__name__)

MACRO_ANALYSIS_PREWARM_INTERVAL_SECONDS = 30 * 60
DAILY_REVIEW_PREWARM_INTERVAL_SECONDS = 30 * 60


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


async def refresh_sge_gold_snapshots() -> None:
    """每日预热上金所全部品种快照。

    上金所按请求频率风控（串行 5s 间隔），若等用户逐个点击品种才拉取，
    首个请求会被整条队列阻塞。这里每日主动预热一次，让页面始终命中本地快照。
    """

    async def iteration():
        from app.financial_data.market.public import warm_up_sge_gold_snapshots

        stats = await warm_up_sge_gold_snapshots()
        if stats["failed"]:
            logger.warning("上金所快照预热存在失败品种: %s", stats)

    await task_scheduler.run_periodic(
        name="sge_gold_snapshot_refresh",
        coro_factory=iteration,
        interval_seconds=60 * 60,
        leader_election=True,
    )


async def refresh_stock_valuation_snapshots() -> None:
    """定期预热用户自选股与持仓股票的每日估值快照。"""

    async def iteration():
        if not get_settings().stock_valuation_snapshot_refresh_enabled:
            return
        from app.financial_data.stock.public import warm_up_valuation_details

        stats = await warm_up_valuation_details()
        if stats.get("failed", 0) > 0:
            logger.warning("自选/持仓估值快照预热存在失败标的: %s", stats)

    await task_scheduler.run_periodic(
        name="stock_valuation_snapshot_refresh",
        coro_factory=iteration,
        interval_seconds=60 * 60,
        leader_election=True,
    )


async def refresh_tdxhub_best_ip() -> None:
    """定期刷新 TDX 行情最优服务器，并顺带充当共享客户端的主动恢复探测器。

    SDK 的建连会对 ``SERVER.HQ`` 做全量并发探测且无短路，一次故障会让客户端
    重建反复付出数十秒代价。这里定期做一次协议级测速，把当前最优节点写回内存
    配置的 ``BESTIP.HQ``，并丢弃可能已经失效的共享客户端，让下一次业务请求用
    新探测结果重建。

    只调用 ``tdxhub.server.server()`` 而不调用 ``tdxhub.server.bestip()``：后者
    会用 SDK 内置默认整体覆盖 ``~/.tdxhub/config.json``，抹掉用户自定义的服务器
    与缓存目录。``BESTIP.HQ`` 在 SDK 里仅作为候选列表的第一个元素被拼进去（探测
    仍是全量并发），所以这里不裁剪候选列表，只提供顺序偏好。
    """

    async def iteration():
        from tdxhub import config as tdxhub_config
        from tdxhub.server import server

        from app.infrastructure.providers.tdxhub import shared_tdxhub_quotes

        def probe() -> list[tuple[str, int]]:
            # tdxhub 未提供类型桩，返回值形状由该库约定（endpoint 二元组列表）
            return cast(list[tuple[str, int]], server(index="HQ", limit=3, sync=False))

        try:
            endpoints = await call_blocking(probe, semaphore=tdxhub_semaphore)
        except Exception as error:
            logger.warning("TDX 行情服务器测速失败: error_type=%s", type(error).__name__)
            return
        if not endpoints:
            logger.warning("TDX 行情服务器测速未发现可用节点")
            return

        # config.update 是递归 merge，只覆盖 BESTIP.HQ 并保留其余兄弟键；
        # 纯内存生效，不落盘（落盘的 setup() 有 _loaded 守卫，运行中不会重载）。
        tdxhub_config.update({"BESTIP": {"HQ": endpoints[0]}})

        if shared_tdxhub_quotes.is_cooling_down():
            # 冷却期内不硬闯，避免与业务请求的重建探测互相争抢带宽。
            logger.info(
                "TDX 客户端处于重建冷却期，本轮仅刷新最优服务器: best=%s remaining=%.1fs",
                endpoints[0],
                shared_tdxhub_quotes.cooldown_remaining_seconds(),
            )
            return

        await call_blocking(shared_tdxhub_quotes.reset, semaphore=tdxhub_semaphore)
        logger.info("TDX 最优服务器已刷新并重置共享客户端: best=%s 备选=%s", endpoints[0], endpoints[1:])

    settings = get_settings()
    await task_scheduler.run_periodic(
        name="tdxhub_bestip_refresh",
        coro_factory=iteration,
        interval_seconds=settings.tdxhub_bestip_refresh_seconds,
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
        if settings.database_backup_include_market_daily:
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

        created: list[Path] = []
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
        interval_seconds=60,
        leader_election=True,
        retry_base_seconds=15,
    )


async def refresh_potential_stocks_daily() -> None:
    """仅在交易日收盘后自动挖掘潜力股。"""
    from app.modules.potential.public import run_scheduled_daily_mining

    async def iteration():
        if not get_settings().potential_stock_daily_enabled:
            return
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


async def refresh_macro_analysis_periodic() -> None:
    """后台预热宏观解读：只为尚未解读的条目调用大模型（已缓存条目零调用）。"""
    from app.financial_data.market.macro.analysis import prewarm_macro_analysis

    async def iteration():
        if not get_settings().macro_analysis_prewarm_enabled:
            return
        interpreted = await prewarm_macro_analysis()
        if interpreted:
            logger.info("宏观解读预热完成: interpreted=%s", interpreted)

    await task_scheduler.run_periodic(
        name="macro_analysis_prewarm",
        coro_factory=iteration,
        interval_seconds=MACRO_ANALYSIS_PREWARM_INTERVAL_SECONDS,
        leader_election=True,
    )


async def refresh_daily_review_periodic() -> None:
    """后台预热每日复盘：收盘后采集并生成一次 AI 复盘写入共享缓存（不落库）。"""
    from app.modules.daily_review.public import prewarm_daily_review

    async def iteration():
        if not get_settings().daily_review_prewarm_enabled:
            return
        warmed = await prewarm_daily_review()
        if warmed:
            logger.info("每日复盘预热完成: warmed=%s", warmed)

    await task_scheduler.run_periodic(
        name="daily_review_prewarm",
        coro_factory=iteration,
        interval_seconds=DAILY_REVIEW_PREWARM_INTERVAL_SECONDS,
        leader_election=True,
    )
