import asyncio
from functools import wraps
from typing import Any, Callable

from tenacity import retry, stop_after_attempt, wait_exponential

_semaphore = asyncio.Semaphore(2)


async def call_blocking(func: Callable, *args: Any, semaphore: asyncio.Semaphore | None = None, **kwargs: Any) -> Any:
    sem = semaphore or _semaphore
    async with sem:
        return await asyncio.to_thread(func, *args, **kwargs)


def with_rate_limit(semaphore: asyncio.Semaphore | None = None) -> Callable:
    sem = semaphore or _semaphore

    def decorator(func: Callable) -> Callable:
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with sem:
                return await asyncio.to_thread(func, *args, **kwargs)

        return wrapper

    return decorator
