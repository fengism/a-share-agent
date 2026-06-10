from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator

from app.models.analysis import AnalysisProgress
from app.services.analysis.pipeline import run_analysis


class AnalysisAlreadyRunningError(RuntimeError):
    """同一股票已有分析任务在运行。"""


_active_analyses: dict[str, asyncio.Task] = {}
_active_analyses_lock = asyncio.Lock()


async def _register_analysis_task(code: str, task: asyncio.Task) -> None:
    """注册运行中的分析任务，防止同一股票重复分析。"""
    async with _active_analyses_lock:
        existing = _active_analyses.get(code)
        if existing is not None and not existing.done():
            raise AnalysisAlreadyRunningError("该股票正在分析中，请稍后")
        _active_analyses[code] = task


async def _unregister_analysis_task(code: str, task: asyncio.Task) -> None:
    """移除当前分析任务，仅在映射中仍是该任务时生效。"""
    async with _active_analyses_lock:
        existing = _active_analyses.get(code)
        if existing is task:
            _active_analyses.pop(code, None)


async def create_analysis_event_generator(code: str) -> AsyncGenerator[dict, None]:
    """创建指定股票的 SSE 事件生成器。"""
    queue: asyncio.Queue[AnalysisProgress | None] = asyncio.Queue()

    async def progress_callback(event: AnalysisProgress) -> None:
        await queue.put(event)

    async def run_and_cleanup() -> None:
        try:
            await run_analysis(code, progress_callback=progress_callback)
        except Exception:
            pass
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_and_cleanup())
    try:
        await _register_analysis_task(code, task)
    except Exception:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        raise

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"comment": "keepalive"}
                    continue

                if event is None:
                    break

                yield {
                    "event": event.type,
                    "data": json.dumps(event.model_dump(), ensure_ascii=False, default=str),
                }
        finally:
            await _unregister_analysis_task(code, task)
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return event_generator()
