"""后台任务健康状态存储与快照。"""

import asyncio
import logging

logger = logging.getLogger(__name__)

background_task_health: dict[str, dict] = {}
_critical_background_tasks: set[str] = set()


def get_task_health(name: str) -> dict:
    return background_task_health.get(name, {"status": "unknown", "last_run": None, "last_error": None})


def new_task_health() -> dict:
    return {
        "status": "starting",
        "last_run": None,
        "last_error": None,
        "consecutive_errors": 0,
        "next_run": None,
        "last_duration_ms": None,
        "role": "local",
        "unexpected_exit": False,
    }


def register_background_task(name: str, *, critical: bool = False) -> dict:
    entry = background_task_health.setdefault(name, new_task_health())
    entry["unexpected_exit"] = False
    if critical:
        _critical_background_tasks.add(name)
    else:
        _critical_background_tasks.discard(name)
    return entry


def critical_background_tasks() -> frozenset[str]:
    return frozenset(_critical_background_tasks)


def clear_critical_background_tasks() -> None:
    _critical_background_tasks.clear()


def monitor_long_running_task(task: asyncio.Task[None], *, critical: bool = False) -> None:
    name = task.get_name()
    entry = register_background_task(name, critical=critical)

    def on_done(completed: asyncio.Task[None]) -> None:
        if completed.cancelled():
            return
        error = completed.exception()
        entry["unexpected_exit"] = True
        entry["next_run"] = None
        if error is None:
            entry["status"] = "stopped"
            entry["last_error"] = "UnexpectedExit"
            logger.error("长驻后台任务意外结束: task=%s", name)
            return
        entry["status"] = "error"
        entry["last_error"] = type(error).__name__
        logger.error(
            "长驻后台任务异常退出: task=%s error_type=%s",
            name,
            type(error).__name__,
            exc_info=(type(error), error, error.__traceback__),
        )

    task.add_done_callback(on_done)


def task_snapshot() -> dict[str, dict]:
    return {
        name: {
            "status": info.get("status", "unknown"),
            "last_run": info.get("last_run"),
            "last_error": info.get("last_error"),
            "consecutive_errors": info.get("consecutive_errors", 0),
            "next_run": info.get("next_run"),
            "last_duration_ms": info.get("last_duration_ms"),
            "role": info.get("role", "local"),
            "unexpected_exit": bool(info.get("unexpected_exit", False)),
        }
        for name, info in background_task_health.items()
    }
