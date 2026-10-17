"""领域事件总线（app.core.events）的调度、去重与关闭语义。"""

import asyncio

import pytest

from app.core.events import AsyncEventBus


async def test_publish_schedules_subscriber_without_blocking_publisher():
    bus = AsyncEventBus()
    seen: list[object] = []

    async def handler(event: object) -> None:
        await asyncio.sleep(0.01)
        seen.append(event)

    bus.subscribe(str, handler)

    await bus.publish("payload")
    # publish 只负责调度，订阅者尚未执行完
    assert seen == []
    assert bus.pending_task_count == 1

    assert await bus.drain(timeout=2) == 0
    assert seen == ["payload"]
    assert bus.pending_task_count == 0


async def test_publish_deduplicates_handler_registered_by_type_and_name():
    bus = AsyncEventBus()
    calls = 0

    async def handler(_: object) -> None:
        nonlocal calls
        calls += 1

    bus.subscribe(str, handler)
    bus.subscribe("named.topic", handler)

    await bus.publish("payload", name="named.topic")
    await bus.drain(timeout=2)

    assert calls == 1


async def test_subscriber_failure_does_not_break_publisher():
    bus = AsyncEventBus()
    seen: list[object] = []

    def boom(_: object) -> None:
        raise RuntimeError("boom")

    async def healthy(event: object) -> None:
        seen.append(event)

    bus.subscribe(int, boom)
    bus.subscribe(int, healthy)

    await bus.publish(1)
    assert await bus.drain(timeout=2) == 0
    assert seen == [1]
    assert bus.pending_task_count == 0


async def test_generic_alias_subscription_does_not_raise():
    """``list[int]`` 不能用于 isinstance，订阅者应被安全跳过而非让 publish 抛错。"""
    bus = AsyncEventBus()
    calls = 0

    def handler(_: object) -> None:
        nonlocal calls
        calls += 1

    bus.subscribe(list[int], handler)  # type: ignore[arg-type]

    await bus.publish("payload")
    assert await bus.drain(timeout=2) == 0
    assert calls == 0


async def test_drain_cancels_subscribers_that_exceed_timeout():
    bus = AsyncEventBus()
    cancelled = False

    async def slow(_: object) -> None:
        nonlocal cancelled
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled = True
            raise

    bus.subscribe(str, slow)
    await bus.publish("payload")

    assert await bus.drain(timeout=0.05) == 1
    assert cancelled is True
    assert bus.pending_task_count == 0


async def test_clear_cancels_pending_tasks_and_removes_subscribers():
    bus = AsyncEventBus()
    calls = 0

    async def handler(_: object) -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(30)

    bus.subscribe(str, handler)
    await bus.publish("payload")
    await asyncio.sleep(0)  # 让订阅者开始执行
    assert calls == 1
    assert bus.pending_task_count == 1

    bus.clear()
    assert bus.pending_task_count == 0

    # 订阅者已清空，后续发布不应再触发任何任务
    await bus.publish("payload")
    await asyncio.sleep(0)
    assert bus.pending_task_count == 0
    assert calls == 1


async def test_unsubscribe_stops_delivery():
    bus = AsyncEventBus()
    calls = 0

    async def handler(_: object) -> None:
        nonlocal calls
        calls += 1

    bus.subscribe("topic", handler)
    bus.unsubscribe("topic", handler)

    await bus.publish("payload", name="topic")
    await bus.drain(timeout=2)

    assert calls == 0


@pytest.mark.parametrize("event_name", ["daily_review.completed", "potential_stocks.mined"])
async def test_publish_without_subscribers_is_a_noop(event_name: str):
    bus = AsyncEventBus()

    await bus.publish(object(), name=event_name)

    assert bus.pending_task_count == 0
