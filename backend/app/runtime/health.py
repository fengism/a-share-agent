import logging
from collections.abc import Callable, Collection

from fastapi.responses import JSONResponse

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.runtime.task_health import critical_background_tasks as get_critical_background_tasks

logger = logging.getLogger(__name__)


def check_database() -> bool:
    from app.infrastructure.persistence.connection import get_connection

    for database in ("market", "user"):
        try:
            get_connection(database).execute("SELECT 1")
        except Exception:
            logger.warning("数据库健康检查失败: database=%s", database, exc_info=True)
            return False
    return True


def check_config_encryption() -> str:
    from app.infrastructure.persistence.user_config_store import config_encryption_status

    try:
        return config_encryption_status()
    except Exception:
        logger.error("敏感配置加密状态检查失败", exc_info=True)
        return "error"


async def readiness_response(
    *,
    database_check: Callable[[], bool] = check_database,
    encryption_check: Callable[[], str] = check_config_encryption,
    background_snapshot: Callable[[], dict[str, dict]],
    critical_background_tasks: Collection[str] | None = None,
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
        not background_tasks.get(name, {}).get("unexpected_exit", False)
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
