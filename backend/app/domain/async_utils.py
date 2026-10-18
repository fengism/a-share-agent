"""Small async helpers shared across layers."""

from __future__ import annotations

import asyncio
from typing import TypeVar

T = TypeVar("T")


async def wait_for_cleanup(task: asyncio.Task[T]) -> T:
    """Await bounded resource cleanup without allowing repeated cancellation to abort it."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


__all__ = ["wait_for_cleanup"]
