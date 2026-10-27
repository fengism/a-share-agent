"""按 key 的异步锁注册表（带引用计数，用完即回收）。

**为什么需要它**：项目里有多处 "同一 key 串行化" 的需求（同一交易日的行情段刷新、
同一 (日期, 用户) 的复盘生成、同一 Prompt 的 LLM 调用、同一股票的复权系数计算）。
最省事的写法是 ``dict.setdefault(key, asyncio.Lock())``，但那份字典**只增不减**：
键随日期/用户数无限增长，进程长跑就会一直攒着历史上所有的 Lock 对象。

**为什么不能简单地"用完就 pop"**：如果 A 持有锁、B 正在等同一个 Lock 对象，
此时 C 进来发现字典空了，会新建一把 Lock 并拿到它——A 和 C 就并发执行了。
对这些锁来说，"并发执行"意味着双份 LLM 调用、双份写库，比几 KB 内存严重得多。

因此这里用**引用计数**：等锁和持锁期间计数 > 0，最后一个引用释放时才删除条目。
删除时字典里已无该 key，任何后来者都会拿到一把全新的锁，而旧锁此时无人持有
（也没有等待者），所以不存在两把锁同时被持有的窗口。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Hashable
from contextlib import asynccontextmanager


class KeyedLockRegistry:
    """按 key 串行化，且在不被引用时自动回收条目。

    典型用法::

        registry = KeyedLockRegistry()

        async with registry.acquire(("600519", "day")):
            ...
    """

    __slots__ = ("_locks", "_refs", "_guard")

    def __init__(self) -> None:
        self._locks: dict[Hashable, asyncio.Lock] = {}
        self._refs: dict[Hashable, int] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: Hashable) -> AsyncIterator[None]:
        """获取 ``key`` 对应的锁并在退出时释放；异常/取消也会正确清理。"""
        async with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            self._refs[key] = self._refs.get(key, 0) + 1
        try:
            async with lock:
                yield
        finally:
            # 不论持有者以何种方式退出（正常返回、抛异常、被取消），都要递减引用。
            async with self._guard:
                remaining = self._refs.get(key, 1) - 1
                if remaining > 0:
                    self._refs[key] = remaining
                else:
                    self._refs.pop(key, None)
                    self._locks.pop(key, None)

    def clear(self) -> None:
        """清空注册表（进程重置/测试用）。

        只应在没有并发使用者的时机调用；已持有旧锁对象的协程会照常跑完，
        后来的请求会拿到新锁，因此不会出现"两把锁同时被持有"。
        """
        self._locks.clear()
        self._refs.clear()

    def active_keys(self) -> int:
        """当前仍有持有者/等待者的 key 数量（用于观测与测试）。"""
        return len(self._locks)

    def tracked_references(self) -> int:
        """当前引用计数总量（用于验证没有泄漏）。"""
        return sum(self._refs.values())


__all__ = ["KeyedLockRegistry"]
