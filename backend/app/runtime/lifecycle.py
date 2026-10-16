from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.configuration import Settings
from app.core.concurrency.rate_limiter import (
    call_blocking,
    configure_blocking_executor,
    database_semaphore,
    misc_semaphore,
    shutdown_blocking_executor,
)
from app.infrastructure.javascript_runtime import initialize_javascript_runtime
from app.runtime.task_supervisor import BackgroundTaskSpec, BackgroundTaskSupervisor

logger = logging.getLogger(__name__)

AsyncTaskFactory = Callable[[], Coroutine[Any, Any, None]]
SupervisedRunner = Callable[[str, AsyncTaskFactory], Coroutine[Any, Any, None]]


def ensure_history_indexes() -> None:
    from app.modules.analysis.persistence.repository import ensure_analysis_history_index
    from app.modules.industry_chain.persistence.repository import ensure_industry_chain_history_index

    ensure_analysis_history_index()
    ensure_industry_chain_history_index()


def load_persisted_global_settings() -> None:
    from app import configuration
    from app.infrastructure.persistence.global_config_store import get_global_config

    persisted = get_global_config()
    if persisted:
        configuration.update_settings(persisted)
        logger.info("已加载持久化全局配置 keys=%s", sorted(persisted))


def verify_database_integrity() -> None:
    """启动时的完整性检查：小库 fail-fast 全检，大库（大表）毫秒级探针检查。

    market/user/industry（约 10 MiB，秒级）执行全量 quick_check；
    market_daily（约 13 GiB，含千万级 market_daily_bars 大表）执行毫秒级探针检查
    （元数据、小表 quick_check、大表首尾叶子页与二级索引探针），兼顾快速启动与损坏预警。

    上次进程正常关机（退出时写了标记）时跳过——损坏只可能来自崩溃/断电。
    """
    from app.infrastructure.persistence.operations import consume_clean_shutdown_marker

    if consume_clean_shutdown_marker():
        logger.info("检测到上次为正常关机，跳过 SQLite 启动完整性检查")
        return

    from app.infrastructure.persistence.operations import (
        verify_startup_critical_databases,
        verify_startup_large_databases,
    )

    verify_startup_critical_databases()
    verify_startup_large_databases()


def mark_database_clean_shutdown() -> None:
    """退出时记录正常关机，供下次启动跳过全库完整性检查。"""
    from app.infrastructure.persistence.operations import mark_clean_shutdown

    mark_clean_shutdown()


def _supervised_task_factory(
    supervised_once: SupervisedRunner,
    name: str,
    factory: AsyncTaskFactory,
) -> AsyncTaskFactory:
    async def run() -> None:
        await supervised_once(name, factory)

    return run


def build_background_task_specs(
    *,
    settings_provider: Callable[[], Settings],
    supervised_once: SupervisedRunner,
    industry_mapping_prewarm: AsyncTaskFactory,
    stock_name_map_prewarm: AsyncTaskFactory,
    hk_stock_search_prewarm: AsyncTaskFactory,
    us_macro_prewarm: AsyncTaskFactory,
    national_team_price_prewarm: AsyncTaskFactory,
    industry_mapping_refresh: AsyncTaskFactory,
    wal_checkpoint: AsyncTaskFactory,
    database_backup: AsyncTaskFactory,
    twitter_feed_refresh: AsyncTaskFactory,
    potential_stock_daily: AsyncTaskFactory,
    market_daily_bar_refresh: AsyncTaskFactory,
    market_daily_backfill_worker: AsyncTaskFactory,
    sge_gold_snapshot_refresh: AsyncTaskFactory,
    tdxhub_bestip_refresh: AsyncTaskFactory,
    macro_analysis_prewarm: AsyncTaskFactory,
    daily_review_prewarm: AsyncTaskFactory,
    stock_valuation_snapshot_refresh: AsyncTaskFactory | None = None,
    bot_job_worker: AsyncTaskFactory,
    quant_strategy_reload: AsyncTaskFactory,
    quant_job_worker: AsyncTaskFactory,
    workflow_job_worker: AsyncTaskFactory,
) -> tuple[BackgroundTaskSpec, ...]:
    return (
        BackgroundTaskSpec(
            name="industry_mapping_prewarm",
            factory=_supervised_task_factory(
                supervised_once,
                "industry_mapping_prewarm",
                industry_mapping_prewarm,
            ),
            start_message="行业映射预热任务已启动",
        ),
        BackgroundTaskSpec(
            name="stock_name_map_prewarm",
            factory=_supervised_task_factory(
                supervised_once,
                "stock_name_map_prewarm",
                stock_name_map_prewarm,
            ),
            start_message="股票名称映射预热任务已启动",
        ),
        BackgroundTaskSpec(
            name="hk_stock_search_prewarm",
            factory=_supervised_task_factory(
                supervised_once,
                "hk_stock_search_prewarm",
                hk_stock_search_prewarm,
            ),
            start_message="港股搜索索引预热任务已启动",
        ),
        BackgroundTaskSpec(
            name="us_macro_prewarm",
            factory=_supervised_task_factory(
                supervised_once,
                "us_macro_prewarm",
                us_macro_prewarm,
            ),
            start_message="美国宏观快照预热任务已启动",
        ),
        BackgroundTaskSpec(
            name="national_team_price_prewarm",
            factory=_supervised_task_factory(
                supervised_once,
                "national_team_price_prewarm",
                national_team_price_prewarm,
            ),
            start_message="国家队行情缓存预热任务已启动",
        ),
        BackgroundTaskSpec(
            name="industry_mapping_refresh",
            factory=industry_mapping_refresh,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="行业映射文件定时更新任务已启动",
        ),
        BackgroundTaskSpec(
            name="wal_checkpoint",
            factory=wal_checkpoint,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="WAL checkpoint 定时任务已启动",
        ),
        BackgroundTaskSpec(
            name="database_backup",
            factory=database_backup,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="SQLite 在线备份任务已启动",
            enabled=lambda: settings_provider().database_backup_enabled,
        ),
        BackgroundTaskSpec(
            name="twitter_feed",
            factory=twitter_feed_refresh,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="Twitter 资讯定时拉取任务已启动",
            enabled=lambda: bool(settings_provider().twitter_feeds),
        ),
        BackgroundTaskSpec(
            name="potential_stock_daily",
            factory=potential_stock_daily,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="每日潜力股挖掘任务已启动",
        ),
        BackgroundTaskSpec(
            name="market_daily_bar_refresh",
            factory=market_daily_bar_refresh,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="盘后历史日线归档任务已启动（实时行情使用独立查询链）",
            enabled=lambda: settings_provider().market_daily_bar_refresh_enabled,
        ),
        BackgroundTaskSpec(
            name="market_daily_backfill_worker",
            factory=market_daily_backfill_worker,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="全市场历史日线回填 Worker 已启动",
        ),
        BackgroundTaskSpec(
            name="sge_gold_snapshot_refresh",
            factory=sge_gold_snapshot_refresh,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="上金所贵金属快照预热已启动",
        ),
        BackgroundTaskSpec(
            name="tdxhub_bestip_refresh",
            factory=tdxhub_bestip_refresh,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="TDX 行情服务器测速与恢复任务已启动",
        ),
        BackgroundTaskSpec(
            name="macro_analysis_prewarm",
            factory=macro_analysis_prewarm,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="宏观解读预热任务已启动",
        ),
        BackgroundTaskSpec(
            name="daily_review_prewarm",
            factory=daily_review_prewarm,
            long_running=True,
            critical=False,
            restart_on_exit=True,
            start_message="每日复盘预热任务已启动",
        ),
        *(
            [
                BackgroundTaskSpec(
                    name="stock_valuation_snapshot_refresh",
                    factory=stock_valuation_snapshot_refresh,
                    long_running=True,
                    critical=False,
                    restart_on_exit=True,
                    start_message="自选与持仓股票估值快照预热已启动",
                )
            ]
            if stock_valuation_snapshot_refresh is not None
            else []
        ),
        BackgroundTaskSpec(
            name="bot_job_worker",
            factory=bot_job_worker,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="Bot 持久化任务 Worker 已启动",
            enabled=lambda: settings_provider().bot_enabled,
        ),
        BackgroundTaskSpec(
            name="quant_strategy_reload",
            factory=quant_strategy_reload,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="量化策略热加载任务已启动",
        ),
        BackgroundTaskSpec(
            name="quant_job_worker",
            factory=quant_job_worker,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="量化回测任务 Worker 已启动",
        ),
        BackgroundTaskSpec(
            name="workflow_job_worker",
            factory=workflow_job_worker,
            long_running=True,
            critical=True,
            restart_on_exit=True,
            start_message="分析 Workflow 持久化任务 Worker 已启动",
        ),
    )


@asynccontextmanager
async def application_lifespan(
    _: FastAPI,
    *,
    settings_provider: Callable[[], Settings],
    supervised_once: SupervisedRunner,
    industry_mapping_refresh: AsyncTaskFactory,
    wal_checkpoint: AsyncTaskFactory,
    database_backup: AsyncTaskFactory,
    twitter_feed_refresh: AsyncTaskFactory,
    potential_stock_daily: AsyncTaskFactory,
    market_daily_bar_refresh: AsyncTaskFactory,
    market_daily_backfill_worker: AsyncTaskFactory,
    sge_gold_snapshot_refresh: AsyncTaskFactory,
    tdxhub_bestip_refresh: AsyncTaskFactory,
    macro_analysis_prewarm: AsyncTaskFactory,
    daily_review_prewarm: AsyncTaskFactory,
    stock_valuation_snapshot_refresh: AsyncTaskFactory | None = None,
    bot_job_worker: AsyncTaskFactory,
    quant_strategy_reload: AsyncTaskFactory,
    quant_job_worker: AsyncTaskFactory,
    workflow_job_worker: AsyncTaskFactory,
    settings_effects_shutdown: AsyncTaskFactory,
    javascript_runtime_initializer: Callable[[], None] = initialize_javascript_runtime,
    history_index_initializer: Callable[[], None] = ensure_history_indexes,
    global_settings_initializer: Callable[[], None] = load_persisted_global_settings,
    database_integrity_checker: Callable[[], None] = verify_database_integrity,
    blocking_runner=call_blocking,
) -> AsyncIterator[None]:
    from app.infrastructure.browser_runtime import ensure_browser_library_paths

    # 必须在任何浏览器子进程（PDF 渲染、stealth 抓取）启动前合入库搜索路径
    ensure_browser_library_paths()
    javascript_runtime_initializer()
    logger.info("JavaScript 运行时初始化完成")

    from app.financial_data.hk.search_index import prewarm_hk_stock_search_index
    from app.financial_data.market.public import prewarm_us_macro_data
    from app.financial_data.market.quotes.national_team import (
        initialize_national_team_refresh,
        prewarm_national_team_prices,
    )
    from app.financial_data.stock.public import build_industry_mapping, build_stock_name_map
    from app.infrastructure.persistence import init_db

    initialize_national_team_refresh()
    configure_blocking_executor(settings_provider().blocking_thread_pool_workers)

    await blocking_runner(init_db, semaphore=database_semaphore)
    logger.info("数据库初始化完成")

    await blocking_runner(database_integrity_checker, semaphore=database_semaphore)
    logger.info("SQLite 启动完整性检查通过（关键小库）")

    await blocking_runner(global_settings_initializer, semaphore=database_semaphore)

    try:
        await blocking_runner(history_index_initializer, semaphore=database_semaphore)
    except Exception:
        logger.warning("历史摘要索引启动回填失败，将在首次访问时重试", exc_info=True)

    from app.infrastructure.persistence.account_store import ensure_default_admin
    from app.infrastructure.persistence.session_store import purge_expired

    seed_password = await blocking_runner(
        ensure_default_admin,
        semaphore=database_semaphore,
    )
    if seed_password:
        admin_name = settings_provider().default_admin_username or "admin"
        logger.warning("=" * 60)
        logger.warning("已创建默认管理员账号（首次登录后必须修改密码）")
        logger.warning("  用户名: %s", admin_name)
        logger.warning("  临时密码: %s", seed_password)
        logger.warning("  该临时密码仅此次打印，请尽快登录并修改。")
        logger.warning("=" * 60)

    try:
        purged = await blocking_runner(
            purge_expired,
            semaphore=database_semaphore,
        )
        logger.info("启动清理过期认证数据: %s", purged)
    except Exception:
        logger.warning("启动清理过期认证数据失败", exc_info=True)

    from app.agentic.bootstrap import register_all_capabilities
    from app.runtime.agentic_tools import configure_application_tools

    configure_application_tools()
    register_all_capabilities()
    logger.info("Chat skills 注册完成")

    from app.modules.quant.public import configure_strategy_registry

    await blocking_runner(
        configure_strategy_registry,
        settings_provider().quant_strategy_dir,
        settings_provider().quant_strategy_hash_ledger_path,
        settings_provider().quant_strategy_publish_dir,
        semaphore=misc_semaphore,
    )
    logger.info("量化策略定义加载完成")

    task_specs = build_background_task_specs(
        settings_provider=settings_provider,
        supervised_once=supervised_once,
        industry_mapping_prewarm=build_industry_mapping,
        stock_name_map_prewarm=build_stock_name_map,
        hk_stock_search_prewarm=prewarm_hk_stock_search_index,
        us_macro_prewarm=prewarm_us_macro_data,
        national_team_price_prewarm=prewarm_national_team_prices,
        industry_mapping_refresh=industry_mapping_refresh,
        wal_checkpoint=wal_checkpoint,
        database_backup=database_backup,
        twitter_feed_refresh=twitter_feed_refresh,
        potential_stock_daily=potential_stock_daily,
        market_daily_bar_refresh=market_daily_bar_refresh,
        market_daily_backfill_worker=market_daily_backfill_worker,
        sge_gold_snapshot_refresh=sge_gold_snapshot_refresh,
        tdxhub_bestip_refresh=tdxhub_bestip_refresh,
        macro_analysis_prewarm=macro_analysis_prewarm,
        daily_review_prewarm=daily_review_prewarm,
        stock_valuation_snapshot_refresh=stock_valuation_snapshot_refresh,
        bot_job_worker=bot_job_worker,
        quant_strategy_reload=quant_strategy_reload,
        quant_job_worker=quant_job_worker,
        workflow_job_worker=workflow_job_worker,
    )
    task_supervisor = BackgroundTaskSupervisor()
    try:
        task_supervisor.start(task_specs)
        yield
    finally:
        await task_supervisor.stop()

        await settings_effects_shutdown()

        from app.financial_data.market.quotes.national_team import shutdown_national_team_refresh

        await shutdown_national_team_refresh()

        from app.infrastructure.http.client import close_session
        from app.infrastructure.llm.runtime import close_async_runtime_pool
        from app.infrastructure.llm.sync_client import close_llm_client_pool
        from app.infrastructure.persistence.connection import close_connection
        from app.modules.market_daily.repository import close_all_connections

        try:
            close_llm_client_pool()
            await close_async_runtime_pool()
        finally:
            try:
                close_session()
            finally:
                # 关闭复用的市场日行情连接，避免退出时残留 WAL 句柄。
                await blocking_runner(close_all_connections, semaphore=database_semaphore)
                try:
                    await blocking_runner(close_connection, semaphore=database_semaphore)
                finally:
                    # 连接全部关闭后再写正常关机标记：下次启动据此跳过全库 quick_check。
                    # 放在 close_connection 之后，确保此刻已无写入者。
                    try:
                        await blocking_runner(
                            mark_database_clean_shutdown, semaphore=database_semaphore,
                        )
                    except Exception:
                        # 写标记失败只会让下次启动多做一次检查，不应影响本次退出。
                        logger.warning("写入正常关机标记失败", exc_info=True)
                    finally:
                        shutdown_blocking_executor()
