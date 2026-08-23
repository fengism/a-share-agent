import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from app.api import setup as api_setup
from app.api.auth.dependencies import require_active_user, require_metrics_access
from app.configuration import configure_user_settings_loader, get_settings
from app.core.concurrency.rate_limiter import call_blocking
from app.infrastructure.persistence.user_config_store import get_user_config
from app.modules.quant.public import run_strategy_reload_watcher
from app.modules.settings import effects as settings_effects
from app.runtime import app_setup, background_tasks, job_workers, logging_setup, task_health, task_scheduler
from app.runtime import health as runtime_health
from app.runtime import lifecycle as runtime_lifecycle

logger = logging.getLogger(__name__)

log_format = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """FastAPI 应用生命周期管理器，启动时初始化数据库与预热任务，关闭时取消任务。"""
    settings = get_settings()

    async def quant_strategy_reload() -> None:
        await run_strategy_reload_watcher(settings.quant_strategy_reload_seconds)

    async with runtime_lifecycle.application_lifespan(
        _,
        settings_provider=get_settings,
        supervised_once=task_scheduler.run_supervised_once,
        industry_mapping_refresh=background_tasks.refresh_industry_mapping_file_daily,
        wal_checkpoint=background_tasks.periodic_wal_checkpoint,
        database_backup=background_tasks.periodic_database_backup,
        twitter_feed_refresh=background_tasks.refresh_twitter_feed_periodic,
        potential_stock_daily=background_tasks.refresh_potential_stocks_daily,
        bot_job_worker=job_workers.run_bot_job_worker,
        quant_strategy_reload=quant_strategy_reload,
        quant_job_worker=job_workers.run_quant_job_worker,
        workflow_job_worker=job_workers.run_workflow_job_worker,
        settings_effects_shutdown=settings_effects.shutdown_update_side_effects,
        history_index_initializer=runtime_lifecycle.ensure_history_indexes,
        global_settings_initializer=runtime_lifecycle.load_persisted_global_settings,
        blocking_runner=call_blocking,
    ):
        yield


async def _readiness_response() -> JSONResponse:
    settings = get_settings()
    return await runtime_health.readiness_response(
        database_check=runtime_health.check_database,
        encryption_check=runtime_health.check_config_encryption,
        background_snapshot=task_health.task_snapshot,
        max_consecutive_failures=settings.background_task_readiness_failure_threshold,
        blocking_runner=call_blocking,
    )


async def readiness():
    """确认数据库可用，失败时返回 503 以停止接收流量。"""
    return await _readiness_response()


async def health():
    """兼容现有部署的就绪检查端点。"""
    return await _readiness_response()


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    settings_provider: Callable[[], Any]
    user_settings_loader: Callable[[int], dict]
    settings_loader_configurer: Callable[[Callable[[int], dict]], None]
    logging_configurer: Callable[[str, str], None]
    lifespan_handler: Callable
    readiness_handler: Callable
    health_handler: Callable
    active_user_dependency: Callable
    metrics_access_dependency: Callable
    operational_snapshot_provider: Callable


def default_application_dependencies() -> ApplicationDependencies:
    return ApplicationDependencies(
        settings_provider=get_settings,
        user_settings_loader=get_user_config,
        settings_loader_configurer=configure_user_settings_loader,
        logging_configurer=logging_setup.configure_logging,
        lifespan_handler=lifespan,
        readiness_handler=readiness,
        health_handler=health,
        active_user_dependency=require_active_user,
        metrics_access_dependency=require_metrics_access,
        operational_snapshot_provider=runtime_health.operational_snapshots,
    )


def create_app(dependencies: ApplicationDependencies | None = None) -> FastAPI:
    dependencies = dependencies or default_application_dependencies()
    dependencies.logging_configurer(log_level, log_format)
    dependencies.settings_loader_configurer(dependencies.user_settings_loader)
    cors_origins = [
        origin.strip()
        for origin in dependencies.settings_provider().cors_origins.split(",")
        if origin.strip()
    ]
    application = app_setup.create_application(
        lifespan=dependencies.lifespan_handler,
        cors_origins=cors_origins,
    )
    api_setup.register_api(
        application,
        active_user_dependencies=[Depends(dependencies.active_user_dependency)],
        readiness_handler=dependencies.readiness_handler,
        health_handler=dependencies.health_handler,
        metrics_access_dependency=dependencies.metrics_access_dependency,
        operational_snapshot_provider=dependencies.operational_snapshot_provider,
    )
    return application


app = create_app()
