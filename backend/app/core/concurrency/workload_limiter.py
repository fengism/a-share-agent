"""按用户和全局维度控制并发工作负载。"""

import asyncio
from collections.abc import Callable


class ConcurrencyLimitExceeded(RuntimeError):
    """用户当前运行中的高成本任务已达到上限。"""


class UserConcurrencyLease:
    def __init__(self, limiter: "UserConcurrencyLimiter", user_id: int) -> None:
        self._limiter = limiter
        self._user_id = user_id
        self._released = False

    async def release(self) -> None:
        if self._released:
            return
        await self._limiter.release(self._user_id)
        self._released = True


class UserConcurrencyLimiter:
    """进程内用户级并发计数器，达到上限时快速失败。"""

    def __init__(self, limit_provider: Callable[[], int]) -> None:
        self._limit_provider = limit_provider
        self._counts: dict[int, int] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: int) -> UserConcurrencyLease:
        limit = max(1, int(self._limit_provider()))
        async with self._lock:
            current = self._counts.get(user_id, 0)
            if current >= limit:
                raise ConcurrencyLimitExceeded(f"用户 {user_id} 的并发任务已达到上限 {limit}")
            self._counts[user_id] = current + 1
        return UserConcurrencyLease(self, user_id)

    async def release(self, user_id: int) -> None:
        async with self._lock:
            current = self._counts.get(user_id, 0)
            if current <= 1:
                self._counts.pop(user_id, None)
            else:
                self._counts[user_id] = current - 1
