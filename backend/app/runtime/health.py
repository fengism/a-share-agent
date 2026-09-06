import logging
from collections.abc import Callable, Collection

from fastapi.responses import JSONResponse

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.operational import OperationalSnapshot
from app.runtime.task_health import critical_background_tasks as get_critical_background_tasks

logger = logging.getLogger(__name__)


def history_index_snapshots() -> dict[str, dict[str, object]]:
    from app.modules.analysis.persistence.repository import analysis_history_index_snapshot
    from app.modules.industry_chain.persistence.repository import industry_chain_history_index_snapshot

    return {
        "analysis": analysis_history_index_snapshot(),
        "industry_chain": industry_chain_history_index_snapshot(),
    }


def check_database() -> bool:
    from app.infrastructure.persistence.connection import ALL_DATABASES, get_connection

    for database in ALL_DATABASES:
        try:
            get_connection(database).execute("SELECT 1")
        except Exception:
            logger.warning("数据库健康检查失败: database=%s", database, exc_info=True)
            return False
    return True


def check_config_encryption() -> str:
    from app.infrastructure.persistence.user_config_store import config_encryption_status

    try:
        return str(config_encryption_status())
    except Exception:
        logger.error("敏感配置加密状态检查失败", exc_info=True)
        return "error"


async def operational_snapshots() -> OperationalSnapshot:
    from app.configuration import get_settings
    from app.core.cache import analysis_cache, cache, market_cache, reference_cache, series_cache
    from app.core.metrics import metrics
    from app.infrastructure.persistence.connection import database_storage_snapshot, default_backup_dir
    from app.infrastructure.persistence.operations import backup_freshness_snapshot
    from app.infrastructure.persistence.workflow_jobs import workflow_job_store
    from app.infrastructure.providers.provider_gateway import provider_gateway
    from app.runtime.task_health import task_snapshot

    settings = get_settings()
    workflow_queue = await call_blocking(
        workflow_job_store.queue_snapshot,
        semaphore=database_semaphore,
    )
    backups = await call_blocking(
        backup_freshness_snapshot,
        settings.database_backup_dir or default_backup_dir(),
        semaphore=database_semaphore,
    )
    databases = await call_blocking(
        database_storage_snapshot,
        semaphore=database_semaphore,
    )
    history_indexes = await call_blocking(
        history_index_snapshots,
        semaphore=database_semaphore,
    )
    application_metrics = metrics.snapshot()
    persistence_metrics = dict(application_metrics.get("persistence", {}))
    persistence_metrics["databases"] = databases
    persistence_metrics["history_indexes"] = history_indexes
    application_metrics["persistence"] = persistence_metrics
    return OperationalSnapshot(
        metrics=application_metrics,
        background_tasks=task_snapshot(),
        workflow_queue=workflow_queue,
        backups=backups,
        global_cache=cache.snapshot(),
        market_cache=market_cache.snapshot(),
        reference_cache=reference_cache.snapshot(),
        analysis_cache=analysis_cache.snapshot(),
        series_cache=series_cache.snapshot(),
        provider_circuits=provider_gateway.snapshot(),
    )


def _critical_task_is_healthy(task: dict, *, max_consecutive_failures: int) -> bool:
    if not task:
        return False
    if task.get("unexpected_exit", False):
        return False
    if task.get("status") == "stopped":
        return False
    threshold = max(1, max_consecutive_failures)
    if int(task.get("consecutive_errors", 0)) >= threshold:
        return False
    return int(task.get("consecutive_restarts", 0)) < threshold


async def readiness_response(
    *,
    database_check: Callable[[], bool] = check_database,
    encryption_check: Callable[[], str] = check_config_encryption,
    background_snapshot: Callable[[], dict[str, dict]],
    critical_background_tasks: Collection[str] | None = None,
    max_consecutive_failures: int = 3,
    blocking_runner=call_blocking,
) -> JSONResponse:
    database_ok = await blocking_runner(database_check, semaphore=database_semaphore)
    encryption_status = "unknown"
    if database_ok:
        encryption_status = await blocking_runner(encryption_check, semaphore=database_semaphore)
    background_tasks = background_snapshot()
    critical_tasks = (
        get_critical_background_tasks()
        if critical_background_tasks is None
        else critical_background_tasks
    )
    background_ok = all(
        _critical_task_is_healthy(
            background_tasks.get(name, {}),
            max_consecutive_failures=max_consecutive_failures,
        )
        for name in critical_tasks
    )
    ready = database_ok and encryption_status != "error" and background_ok
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "error",
            "database": "connected" if database_ok else "error",
            "config_encryption": encryption_status,
            "background_tasks": background_tasks,
        },
    )
