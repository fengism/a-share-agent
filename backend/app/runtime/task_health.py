"""后台任务健康状态存储与快照。"""

import asyncio
import logging

logger = logging.getLogger(__name__)

background_task_health: dict[str, dict] = {}
_critical_background_tasks: set[str] = set()
_readiness_background_tasks: set[str] = set()


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
        # 「按配置停用」与「崩溃退出」都会把 status 写成 stopped，两者对
        # readiness 的含义相反：前者是预期状态，后者是故障。用独立标记区分，
        # 避免 bot_enabled=false 这类正常配置把就绪探测永久拉挂。
        "disabled_by_config": False,
        # 「已按正常路径退出」（关闭/取消），与崩溃区分。
        "cancelled_cleanly": False,
        "restart_count": 0,
        "consecutive_restarts": 0,
        "last_restart_at": None,
        "last_restart_error": None,
    }


def register_background_task(
    name: str,
    *,
    critical: bool = False,
    readiness_required: bool = False,
) -> dict:
    entry = background_task_health.setdefault(name, new_task_health())
    entry["unexpected_exit"] = False
    entry["disabled_by_config"] = False
    entry["cancelled_cleanly"] = False
    if critical:
        _critical_background_tasks.add(name)
    else:
        _critical_background_tasks.discard(name)
    if readiness_required:
        _readiness_background_tasks.add(name)
    else:
        _readiness_background_tasks.discard(name)
    return entry


def mark_task_disabled_by_config(name: str) -> None:
    """标记任务因配置禁用而停止：这是预期状态，不应拉垮就绪探测。"""
    entry = background_task_health.get(name)
    if entry is None:
        return
    entry["status"] = "stopped"
    entry["disabled_by_config"] = True
    entry["unexpected_exit"] = False
    entry["next_run"] = None


def mark_task_cancelled(name: str) -> None:
    """进程内正常取消（如应用关闭）：不算故障，也不冒充配置禁用。

    保留 ``status=stopped`` 供人排查，但清掉故障计数并由 ``cancelled_cleanly``
    说明原因——否则应用正常关闭期间就绪探测会抛 503，把「正在退出」误报成
    「服务坏了」。
    """
    entry = background_task_health.get(name)
    if entry is None:
        return
    entry["status"] = "stopped"
    entry["disabled_by_config"] = False
    entry["cancelled_cleanly"] = True
    entry["consecutive_errors"] = 0
    entry["consecutive_restarts"] = 0
    entry["unexpected_exit"] = False


def critical_background_tasks() -> frozenset[str]:
    return frozenset(_critical_background_tasks)


def readiness_background_tasks() -> frozenset[str]:
    return frozenset(_readiness_background_tasks)


def clear_critical_background_tasks() -> None:
    _critical_background_tasks.clear()
    _readiness_background_tasks.clear()


def monitor_long_running_task(
    task: asyncio.Task[None],
    *,
    critical: bool = False,
    readiness_required: bool = False,
) -> None:
    name = task.get_name()
    entry = register_background_task(
        name,
        critical=critical,
        readiness_required=readiness_required,
    )

    def on_done(completed: asyncio.Task[None]) -> None:
        if completed.cancelled():
            # 正常取消（应用关闭 / 配置停用）不是故障；记录原因，
            # 避免健康快照永远停在 starting。
            mark_task_cancelled(name)
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
            "disabled_by_config": bool(info.get("disabled_by_config", False)),
            "cancelled_cleanly": bool(info.get("cancelled_cleanly", False)),
            "restart_count": info.get("restart_count", 0),
            "consecutive_restarts": info.get("consecutive_restarts", 0),
            "last_restart_at": info.get("last_restart_at"),
            "last_restart_error": info.get("last_restart_error"),
            # critical 与 readiness_required 是两种不同的运维动作：
            # critical 决定「值不值得告警」，readiness_required 决定「要不要摘掉流量」。
            # 两者都导出，否则 critical 标记就没任何消费方。
            "critical": name in _critical_background_tasks,
            "readiness_required": name in _readiness_background_tasks,
        }
        for name, info in background_task_health.items()
    }
