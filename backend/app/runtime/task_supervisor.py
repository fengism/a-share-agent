"""后台任务声明、启动、监督与关闭。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from app.runtime.task_health import monitor_long_running_task

logger = logging.getLogger(__name__)

AsyncTaskFactory = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class BackgroundTaskSpec:
    name: str
    factory: AsyncTaskFactory
    long_running: bool = False
    critical: bool = False
    start_message: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("后台任务名称不能为空")
        if self.critical and not self.long_running:
            raise ValueError("关键后台任务必须是长驻任务")


class BackgroundTaskSupervisor:
    """Own all application background tasks and stop them as one unit."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def task_names(self) -> tuple[str, ...]:
        return tuple(self._tasks)

    def start(self, specs: Iterable[BackgroundTaskSpec]) -> None:
        if self._tasks:
            raise RuntimeError("后台任务监督器已启动")
        task_specs = tuple(specs)
        names = [spec.name for spec in task_specs]
        if len(names) != len(set(names)):
            raise ValueError("后台任务名称重复")

        for spec in task_specs:
            task = asyncio.create_task(spec.factory(), name=spec.name)
            self._tasks[spec.name] = task
            if spec.long_running:
                monitor_long_running_task(task, critical=spec.critical)
            if spec.start_message:
                logger.info(spec.start_message)

    async def stop(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
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
