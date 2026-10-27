"""按 key 的锁注册表：串行化语义 + 用完回收。

重点是这两条不能同时丢：既要"同 key 串行"，又要"没人用了就删条目"。任何"直接
``pop``"的实现都会在 A 持锁、B 排队时让 C 新建另一把锁，从而与 A 并发执行。
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.concurrency.keyed_lock import KeyedLockRegistry

pytestmark = pytest.mark.anyio


async def test_same_key_is_serialized_and_entry_is_released() -> None:
    registry = KeyedLockRegistry()
    events: list[str] = []
    holder_entered = asyncio.Event()
    release_holder = asyncio.Event()

    async def holder() -> None:
        async with registry.acquire("k"):
            events.append("a:enter")
            holder_entered.set()
            await release_holder.wait()
            events.append("a:exit")

    async def waiter() -> None:
        async with registry.acquire("k"):
            events.append("b:enter")

    task_a = asyncio.create_task(holder())
    await holder_entered.wait()
    task_b = asyncio.create_task(waiter())
    # 让出一次控制权，确认 b 确实被挡在锁外。
    await asyncio.sleep(0)
    assert "b:enter" not in events
    release_holder.set()
    await asyncio.gather(task_a, task_b)

    assert events == ["a:enter", "a:exit", "b:enter"]
    assert registry.active_keys() == 0
    assert registry.tracked_references() == 0


async def test_different_keys_run_concurrently() -> None:
    registry = KeyedLockRegistry()
    both = asyncio.Event()
    running: set[str] = set()

    async def worker(name: str) -> None:
        async with registry.acquire(name):
            running.add(name)
            if len(running) == 2:
                both.set()
            await both.wait()

    await asyncio.wait_for(
        asyncio.gather(worker("x"), worker("y")), timeout=2.0,
    )
    assert both.is_set()
    assert registry.active_keys() == 0


async def test_waiters_share_one_lock_and_cleanup_happens_after_last_release() -> None:
    registry = KeyedLockRegistry()
    entered = asyncio.Event()
    release = asyncio.Event()
    holders: list[int] = []
    concurrent_peak = 0

    async def worker() -> None:
        nonlocal concurrent_peak
        async with registry.acquire("shared"):
            holders.append(1)
            concurrent_peak = max(concurrent_peak, len(holders))
            entered.set()
            await release.wait()
            holders.pop()

    tasks = [asyncio.create_task(worker()) for _ in range(3)]
    await entered.wait()
    # 三个协程都在注册表里登记过引用，因此条目不会被提前删除。
    assert registry.active_keys() == 1
    release.set()
    await asyncio.gather(*tasks)

    assert concurrent_peak == 1
    assert registry.active_keys() == 0
    assert registry.tracked_references() == 0


async def test_exception_still_releases_and_cleans_up() -> None:
    registry = KeyedLockRegistry()
    with pytest.raises(RuntimeError):
        async with registry.acquire("boom"):
            raise RuntimeError("boom")
    assert registry.active_keys() == 0
    # 释放后仍可再次获取
    async with registry.acquire("boom"):
        assert registry.active_keys() == 1


async def test_cancellation_still_releases_and_cleans_up() -> None:
    registry = KeyedLockRegistry()
    entered = asyncio.Event()

    async def victim() -> None:
        async with registry.acquire("cancel"):
            entered.set()
            await asyncio.sleep(30)

    task = asyncio.create_task(victim())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert registry.active_keys() == 0
    assert registry.tracked_references() == 0


async def test_clear_is_safe_for_subsequent_use() -> None:
    registry = KeyedLockRegistry()
    async with registry.acquire("k"):
        registry.clear()
        assert registry.active_keys() == 0
    # 退出时不能因为条目已被清除而抛 KeyError
    assert registry.tracked_references() == 0
