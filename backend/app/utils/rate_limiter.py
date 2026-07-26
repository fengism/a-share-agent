import asyncio
from functools import wraps
from typing import Any, Callable

from tenacity import retry, stop_after_attempt, wait_exponential

_semaphore = asyncio.Semaphore(2)

# ── 按数据源拆分的信号量，避免互相争抢 ──
eastmoney_semaphore = asyncio.Semaphore(3)
akshare_semaphore = asyncio.Semaphore(2)
tencent_semaphore = asyncio.Semaphore(2)
sina_semaphore = asyncio.Semaphore(2)
ths_semaphore = asyncio.Semaphore(2)
iwencai_semaphore = asyncio.Semaphore(1)
baidu_semaphore = asyncio.Semaphore(2)
cls_semaphore = asyncio.Semaphore(2)
tdx_semaphore = asyncio.Semaphore(2)
misc_semaphore = asyncio.Semaphore(4)


async def call_blocking(func: Callable, *args: Any, semaphore: asyncio.Semaphore | None = None, **kwargs: Any) -> Any:
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
        return await asyncio.to_thread(func, *args, **kwargs)


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
                return await asyncio.to_thread(func, *args, **kwargs)

        # 在 retry 包装之后再复制元数据，确保最终返回对象的 __name__/__wrapped__
        # 指向原函数（retry 会覆盖内层的 @wraps 结果，破坏 introspection 链）。
        return wraps(func)(wrapper)

    return decorator
