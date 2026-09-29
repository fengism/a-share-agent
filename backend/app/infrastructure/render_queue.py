"""Shared FIFO admission for PDF and PNG work on one backend event loop.

Slot handoff reserves capacity before waking a waiter. Release and quarantine are
synchronous: cancellation cannot interrupt permit bookkeeping. Renderer cleanup
must finish before exiting the slot.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from weakref import WeakKeyDictionary

from app.configuration import get_settings
from app.core.exceptions import UpstreamUnavailableError


def _quarantine_error() -> UpstreamUnavailableError:
    return UpstreamUnavailableError("渲染资源未完成清理，请重启后端后重试", code="render.cleanup_failed")


class RenderLimiter:
    def __init__(self, concurrency: int, max_waiters: int) -> None:
        if concurrency < 1 or max_waiters < 0:
            raise ValueError("Invalid render queue capacity")
        self.concurrency = concurrency
        self.max_waiters = max_waiters
        self.active = 0
        self._waiters: deque[asyncio.Future[None]] = deque()
        self._quarantined = False

    @property
    def waiters(self) -> int:
        return sum(not waiter.done() for waiter in self._waiters)

    @property
    def quarantined(self) -> bool:
        return self._quarantined

    @quarantined.setter
    def quarantined(self, value: bool) -> None:
        if self._quarantined and not value:
            raise ValueError("Quarantined render queues must be replaced, not reopened")
        self._quarantined = value
        self._dispatch()

    def _dispatch(self) -> None:
        while self._waiters:
            waiter = self._waiters[0]
            if waiter.done():
                self._waiters.popleft()
                continue
            if self._quarantined:
                self._waiters.popleft().set_exception(_quarantine_error())
            elif self.active < self.concurrency:
                self.active += 1
                self._waiters.popleft().set_result(None)
            else:
                break

    def _release(self) -> None:
        self.active -= 1
        self._dispatch()

    async def _acquire(self) -> None:
        if self._quarantined:
            raise _quarantine_error()
        self._dispatch()
        if self.active < self.concurrency and not self._waiters:
            self.active += 1
            return
        if self.waiters >= self.max_waiters:
            raise UpstreamUnavailableError("PDF/图表渲染队列已满，请稍后重试", code="pdf.queue_full")
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            await waiter
        except BaseException:
            # Cancellation can arrive after a slot was handed off but before the
            # waiter resumed. Return that reserved slot exactly once.
            if waiter.done() and not waiter.cancelled() and waiter.exception() is None:
                self.active -= 1
            else:
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
            self._dispatch()
            raise
        if self._quarantined:
            self._release()
            raise _quarantine_error()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self._acquire()
        try:
            yield
        finally:
            self._release()


_limiters: WeakKeyDictionary[asyncio.AbstractEventLoop, RenderLimiter] = WeakKeyDictionary()


def get_render_limiter() -> RenderLimiter:
    loop = asyncio.get_running_loop()
    if loop not in _limiters:
        settings = get_settings()
        _limiters[loop] = RenderLimiter(settings.pdf_max_concurrency, settings.pdf_max_waiters)
    return _limiters[loop]
