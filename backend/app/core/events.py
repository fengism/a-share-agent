"""轻量级进程内异步领域事件总线（In-Process Async Event Bus）。

实现领域模块之间的彻底解耦：
- 生产者（如每日复盘、潜力股挖掘、异动监控）只需发布领域事件，无需知晓下游消费者的存在。
- 消费者（如消息推送、数据归档、统计分析）只需订阅关心的事件类型。
- 订阅者执行在异步后台任务中，单处理者抛错不影响发布者与其他处理者。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

EventT = TypeVar("EventT")
EventHandler = Callable[[EventT], Coroutine[Any, Any, None] | None]

# ``publish`` 只做调度，订阅者任务在后台运行；进程退出或测试隔离时需要等待它们的上限。
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5.0


def _matches(event: Any, expected: type) -> bool:
    """安全判断事件是否属于订阅类型。

    ``list[int]`` 这类泛型别名不能用于 ``isinstance``（会抛 ``TypeError``），
    而 ``publish`` 的契约是绝不向发布者抛错，因此这里降级为不匹配。
    """
    try:
        return isinstance(event, expected)
    except TypeError:
        return False


@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类。"""
    pass


class AsyncEventBus:
    """异步进程内事件总线。"""

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler[Any]]] = defaultdict(list)
        self._named_handlers: dict[str, list[EventHandler[Any]]] = defaultdict(list)
        # 必须持有 task 强引用：asyncio 只保留弱引用，未持有引用的任务可能在
        # 执行前被垃圾回收（官方文档明确警告）。
        self._pending_tasks: set[asyncio.Task[None]] = set()

    def subscribe(self, event_type_or_name: type | str, handler: EventHandler[Any]) -> None:
        """订阅指定事件类型或事件名称。"""
        if isinstance(event_type_or_name, str):
            if handler not in self._named_handlers[event_type_or_name]:
                self._named_handlers[event_type_or_name].append(handler)
        else:
            if handler not in self._handlers[event_type_or_name]:
                self._handlers[event_type_or_name].append(handler)

    def unsubscribe(self, event_type_or_name: type | str, handler: EventHandler[Any]) -> None:
        """取消订阅。"""
        if isinstance(event_type_or_name, str):
            if handler in self._named_handlers[event_type_or_name]:
                self._named_handlers[event_type_or_name].remove(handler)
        else:
            if handler in self._handlers[event_type_or_name]:
                self._handlers[event_type_or_name].remove(handler)

    async def publish(self, event: Any, *, name: str = "") -> None:
        """发布领域事件，非阻塞异步调度所有已注册的订阅者。"""
        handlers: list[EventHandler[Any]] = []

        # 1. 按具体事件类型查找处理器（isinstance 已覆盖子类）
        event_cls = type(event)
        for registered_type, registered_handlers in self._handlers.items():
            if _matches(event, registered_type):
                handlers.extend(registered_handlers)

        # 2. 按命名查找处理器
        event_name = name or getattr(event, "event_name", "") or event_cls.__name__
        if event_name in self._named_handlers:
            handlers.extend(self._named_handlers[event_name])

        if not handlers:
            return

        # 去重相同处理器
        unique_handlers: list[EventHandler[Any]] = []
        for h in handlers:
            if h not in unique_handlers:
                unique_handlers.append(h)

        async def _safe_execute(handler: EventHandler[Any]) -> None:
            try:
                res = handler(event)
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:  # noqa: BLE001 - 单一订阅者异常不应阻断
                logger.warning(
                    "事件处理异常 event=%s handler=%s error=%s",
                    event_name,
                    getattr(handler, "__name__", str(handler)),
                    exc,
                    exc_info=True,
                )

        # 启动后台任务并发执行，不阻断发布者
        for handler in unique_handlers:
            self._track(asyncio.create_task(_safe_execute(handler), name=f"event:{event_name}"))

    def _track(self, task: asyncio.Task[None]) -> None:
        self._pending_tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        self._pending_tasks.discard(task)
        if task.cancelled():
            return
        # ``_safe_execute`` 已吞掉订阅者异常，这里是最后的兜底观测点。
        if (error := task.exception()) is not None:
            logger.warning("事件订阅者任务异常退出 error=%s", error, exc_info=error)

    @property
    def pending_task_count(self) -> int:
        """当前尚未完成的订阅者任务数（供健康检查与测试观测）。"""
        return len(self._pending_tasks)

    async def drain(self, timeout: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS) -> int:
        """等待未完成的订阅者任务；超时后取消并返回被取消的数量。

        进程退出前调用，避免「事件已发布但订阅者尚未落库/推送」的丢失。
        """
        pending = [task for task in self._pending_tasks if not task.done()]
        if not pending:
            return 0
        _, still_pending = await asyncio.wait(pending, timeout=timeout)
        for task in still_pending:
            task.cancel()
        if still_pending:
            await asyncio.gather(*still_pending, return_exceptions=True)
            logger.warning("事件订阅者任务未在 %.1fs 内完成，已取消 %d 个", timeout, len(still_pending))
        return len(still_pending)

    def clear(self) -> None:
        """清除所有订阅者并取消未完成的调度任务（主要供测试隔离）。"""
        self._handlers.clear()
        self._named_handlers.clear()
        for task in list(self._pending_tasks):
            task.cancel()
        self._pending_tasks.clear()


# 全局共享事件总线单例
event_bus = AsyncEventBus()
