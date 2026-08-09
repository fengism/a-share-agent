"""Small progress-reporting primitives shared by long-running workflows."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

EventT = TypeVar("EventT")
ProgressCallback = Callable[[EventT], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ProgressEmitter(Generic[EventT]):
    callback: ProgressCallback[EventT] | None = None

    async def emit(self, event: EventT) -> None:
        if self.callback is not None:
            await self.callback(event)


@dataclass(frozen=True, slots=True)
class StageClock:
    started_at: float

    @classmethod
    def start(cls) -> "StageClock":
        return cls(started_at=time.monotonic())

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started_at) * 1000)


__all__ = ["ProgressCallback", "ProgressEmitter", "StageClock"]
