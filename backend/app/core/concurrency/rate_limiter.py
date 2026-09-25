"""共享并发信号量与阻塞函数调度。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import partial, wraps
from threading import Lock
from typing import Any, Callable, TypeVar

from tenacity import retry, stop_after_attempt, wait_exponential

T = TypeVar("T")

_semaphore = asyncio.Semaphore(2)

# ── 按数据源拆分的信号量，避免互相争抢 ──
eastmoney_semaphore = asyncio.Semaphore(1)
exchange_semaphore = asyncio.Semaphore(2)
akshare_semaphore = asyncio.Semaphore(2)
tencent_semaphore = asyncio.Semaphore(2)
sina_semaphore = asyncio.Semaphore(2)
ths_semaphore = asyncio.Semaphore(2)
iwencai_semaphore = asyncio.Semaphore(1)
baidu_semaphore = asyncio.Semaphore(2)
cls_semaphore = asyncio.Semaphore(2)
kaipanhong_semaphore = asyncio.Semaphore(1)
tdx_semaphore = asyncio.Semaphore(2)
tdxhub_semaphore = tdx_semaphore
misc_semaphore = asyncio.Semaphore(4)
database_semaphore = asyncio.Semaphore(8)

_blocking_executor: ThreadPoolExecutor | None = None
_blocking_executor_lock = Lock()


def configure_blocking_executor(max_workers: int) -> None:
    global _blocking_executor
    executor = ThreadPoolExecutor(
        max_workers=max(1, max_workers),
        thread_name_prefix="app-blocking",
    )
    with _blocking_executor_lock:
        previous = _blocking_executor
        _blocking_executor = executor
    if previous is not None:
        previous.shutdown(wait=True, cancel_futures=True)


def shutdown_blocking_executor() -> None:
    global _blocking_executor
    with _blocking_executor_lock:
        executor = _blocking_executor
        _blocking_executor = None
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)


async def _run_blocking(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    with _blocking_executor_lock:
        executor = _blocking_executor
    if executor is None:
        return await asyncio.to_thread(func, *args, **kwargs)
    loop = asyncio.get_running_loop()
    context = copy_context()
    call = partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, context.run, call)


async def call_blocking(
    func: Callable[..., T],
    *args: Any,
    semaphore: asyncio.Semaphore | None = None,
    **kwargs: Any,
) -> T:
    """Run a blocking function in a thread under an asyncio semaphore.

    Param:
        func: blocking callable to execute
        *args: positional arguments forwarded to func
        semaphore: optional semaphore to use (defaults to module-level _semaphore)
        **kwargs: keyword arguments forwarded to func
    Return:
        return value from func
    """
    sem = semaphore or _semaphore
    async with sem:
        return await _run_blocking(func, *args, **kwargs)


def with_rate_limit(semaphore: asyncio.Semaphore | None = None) -> Callable:
    """Build a decorator that runs an async function under a semaphore with retry.

    Param:
        semaphore: optional semaphore to use (defaults to module-level _semaphore)
    Return:
        a decorator that wraps the function with semaphore control and tenacity retry
    """
    sem = semaphore or _semaphore

    def decorator(func: Callable) -> Callable:
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with sem:
                return await _run_blocking(func, *args, **kwargs)

        # 在 retry 包装之后再复制元数据，确保最终返回对象的 __name__/__wrapped__
        # 指向原函数（retry 会覆盖内层的 @wraps 结果，破坏 introspection 链）。
        return wraps(func)(wrapper)

    return decorator
