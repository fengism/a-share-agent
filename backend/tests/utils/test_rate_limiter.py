"""单元测试：rate_limiter 的 call_blocking 和 with_rate_limit。"""
import asyncio
import time

import pytest

from app.utils.rate_limiter import call_blocking, with_rate_limit


def _blocking_add(a: int, b: int) -> int:
    """Simple blocking function for testing."""
    return a + b


def _blocking_slow(delay: float) -> str:
    """Simulate a slow blocking operation."""
    time.sleep(delay)
    return "done"


@pytest.mark.asyncio
async def test_call_blocking_basic():
    result = await call_blocking(_blocking_add, 3, 4)
    assert result == 7


@pytest.mark.asyncio
async def test_call_blocking_with_custom_semaphore():
    sem = asyncio.Semaphore(1)
    result = await call_blocking(_blocking_add, 1, 2, semaphore=sem)
    assert result == 3


@pytest.mark.asyncio
async def test_call_blocking_concurrent_limit():
    """验证 semaphore 限制并发数。"""
    sem = asyncio.Semaphore(1)
    start = time.monotonic()

    async def run():
        await call_blocking(_blocking_slow, 0.2, semaphore=sem)

    t1 = asyncio.create_task(run())
    t2 = asyncio.create_task(run())
    await asyncio.gather(t1, t2)
    elapsed = time.monotonic() - start
    # 串行执行，总耗时应该 >= 0.4s
    assert elapsed >= 0.4


@pytest.mark.asyncio
async def test_with_rate_limit_decorator():
    decorated = with_rate_limit()(_blocking_add)
    result = await decorated(10, 20)
    assert result == 30


def test_call_blocking_sync_wrapper():
    """验证修饰器语法不影响函数元数据。"""
    decorated = with_rate_limit()(_blocking_add)
    assert decorated.__name__ == "_blocking_add"
    assert decorated.__wrapped__ is _blocking_add
