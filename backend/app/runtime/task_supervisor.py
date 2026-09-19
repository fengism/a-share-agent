"""后台任务声明、启动、监督与关闭。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.runtime.task_health import monitor_long_running_task, register_background_task

logger = logging.getLogger(__name__)

AsyncTaskFactory = Callable[[], Coroutine[Any, Any, None]]
TaskEnabledPredicate = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class BackgroundTaskSpec:
    name: str
    factory: AsyncTaskFactory
    long_running: bool = False
    critical: bool = False
    readiness_required: bool = False
    start_message: str | None = None
    restart_on_exit: bool = False
    restart_base_seconds: float = 1.0
    restart_max_seconds: float = 60.0
    restart_reset_seconds: float = 60.0
    enabled: TaskEnabledPredicate | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("后台任务名称不能为空")
        if self.critical and not self.long_running:
            raise ValueError("关键后台任务必须是长驻任务")
        if self.readiness_required and not self.long_running:
            raise ValueError("readiness 依赖的后台任务必须是长驻任务")
        if self.restart_on_exit and not self.long_running:
            raise ValueError("只有长驻任务可以配置自动重启")
        if self.restart_base_seconds <= 0:
            raise ValueError("重启基础退避必须大于 0")
        if self.restart_max_seconds < self.restart_base_seconds:
            raise ValueError("重启最大退避不能小于基础退避")
        if self.restart_reset_seconds < 0:
            raise ValueError("重启计数重置时间不能小于 0")


class BackgroundTaskSupervisor:
    """Own all application background tasks and stop them as one unit."""

    def __init__(self, *, condition_poll_seconds: float = 5.0) -> None:
        if condition_poll_seconds <= 0:
            raise ValueError("条件任务检查间隔必须大于 0")
        self._condition_poll_seconds = condition_poll_seconds
        self._specs: dict[str, BackgroundTaskSpec] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._condition_task: asyncio.Task[None] | None = None
        self._reconcile_lock = asyncio.Lock()
        self._started = False

    @property
    def task_names(self) -> tuple[str, ...]:
        return tuple(self._tasks)

    async def _run_spec(self, spec: BackgroundTaskSpec) -> None:
        entry = register_background_task(
            spec.name,
            critical=spec.critical,
            readiness_required=spec.readiness_required,
        )
        consecutive_restarts = 0
        while True:
            started_at = time.monotonic()
            restart_error = "UnexpectedExit"
            try:
                await spec.factory()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                restart_error = type(error).__name__
                if not spec.restart_on_exit:
                    raise
                logger.error(
                    "后台任务异常退出，准备重启: task=%s error_type=%s",
                    spec.name,
                    restart_error,
                    exc_info=(type(error), error, error.__traceback__),
                )
            else:
                if not spec.restart_on_exit:
                    return
                logger.error("后台任务意外结束，准备重启: task=%s", spec.name)

            runtime_seconds = time.monotonic() - started_at
            if runtime_seconds >= spec.restart_reset_seconds:
                consecutive_restarts = 0
            consecutive_restarts += 1
            delay = min(
                spec.restart_max_seconds,
                spec.restart_base_seconds * (2 ** (consecutive_restarts - 1)),
            )
            entry["status"] = "restarting"
            entry["last_error"] = restart_error
            entry["restart_count"] = int(entry.get("restart_count", 0)) + 1
            entry["consecutive_restarts"] = consecutive_restarts
            entry["last_restart_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            entry["last_restart_error"] = restart_error
            entry["unexpected_exit"] = False
            entry["next_run"] = datetime.fromtimestamp(
                datetime.now(UTC).timestamp() + delay,
                tz=UTC,
            ).isoformat(timespec="seconds")
            await asyncio.sleep(delay)
            entry["status"] = "starting"
            entry["next_run"] = None

    def _start_spec(self, spec: BackgroundTaskSpec) -> None:
        task = asyncio.create_task(self._run_spec(spec), name=spec.name)
        self._tasks[spec.name] = task
        if spec.long_running:
            monitor_long_running_task(
                task,
                critical=spec.critical,
                readiness_required=spec.readiness_required,
            )
        if spec.start_message:
            logger.info(spec.start_message)

    @staticmethod
    def _is_enabled(spec: BackgroundTaskSpec) -> bool:
        return spec.enabled is None or spec.enabled()

    async def reconcile(self) -> None:
        """Apply current enable predicates without restarting unaffected tasks."""
        async with self._reconcile_lock:
            if not self._started:
                return
            for spec in self._specs.values():
                if spec.enabled is None:
                    continue
                try:
                    enabled = self._is_enabled(spec)
                except Exception:
                    logger.exception("后台任务启用条件检查失败，保留当前状态: task=%s", spec.name)
                    continue

                task = self._tasks.get(spec.name)
                if enabled and task is None:
                    self._start_spec(spec)
                    continue
                if enabled or task is None:
                    continue

                task.cancel()
                result = await asyncio.gather(task, return_exceptions=True)
                if self._tasks.get(spec.name) is task:
                    self._tasks.pop(spec.name, None)
                error = result[0]
                if isinstance(error, BaseException) and not isinstance(error, asyncio.CancelledError):
                    logger.error(
                        "条件后台任务停止异常 task=%s error_type=%s",
                        spec.name,
                        type(error).__name__,
                    )
                logger.info("后台任务已按配置停止: task=%s", spec.name)

    async def _run_condition_reconciler(self) -> None:
        while True:
            await asyncio.sleep(self._condition_poll_seconds)
            await self.reconcile()

    def start(self, specs: Iterable[BackgroundTaskSpec]) -> None:
        if self._started:
            raise RuntimeError("后台任务监督器已启动")
        task_specs = tuple(specs)
        names = [spec.name for spec in task_specs]
        if len(names) != len(set(names)):
            raise ValueError("后台任务名称重复")

        self._specs = {spec.name: spec for spec in task_specs}
        self._started = True
        for spec in task_specs:
            try:
                enabled = self._is_enabled(spec)
            except Exception:
                logger.exception("后台任务启用条件初始检查失败，暂不启动: task=%s", spec.name)
                continue
            if enabled:
                self._start_spec(spec)
            else:
                logger.info("后台任务已按配置禁用: task=%s", spec.name)

        if any(spec.enabled is not None for spec in task_specs):
            self._condition_task = asyncio.create_task(
                self._run_condition_reconciler(),
                name="background_task_condition_reconciler",
            )

    async def stop(self) -> None:
        self._started = False
        condition_task = self._condition_task
        self._condition_task = None
        if condition_task is not None:
            condition_task.cancel()
            await asyncio.gather(condition_task, return_exceptions=True)

        async with self._reconcile_lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
            self._specs.clear()
            for task in tasks:
                task.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for task, result in zip(tasks, results):
                if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                    logger.error(
                        "后台任务关闭异常 task=%s error_type=%s",
                        task.get_name(),
                        type(result).__name__,
                    )
