"""个股分析 SSE 任务适配。"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from app.core.concurrency.task_stream import KeyedTaskEventStream
from app.modules.analysis.events import AnalysisProgress
from app.modules.analysis.pipeline import run_analysis

logger = logging.getLogger(__name__)


class AnalysisAlreadyRunningError(RuntimeError):
    """同一股票已有分析任务在运行。"""


_analysis_stream = KeyedTaskEventStream[AnalysisProgress](
    lambda: AnalysisAlreadyRunningError("该股票正在分析中，请稍后")
)
_active_analyses = _analysis_stream.active_tasks


async def create_analysis_event_generator(code: str, user_id: int) -> AsyncGenerator[dict, None]:
    """创建指定股票的 SSE 事件生成器。"""

    async def runner(progress_callback) -> None:
        await run_analysis(code, user_id, progress_callback=progress_callback)

    def log_error(error: Exception) -> None:
        logger.error(
            "个股分析后台任务异常退出: code=%s, error=%s",
            code,
            error,
            exc_info=True,
        )

    return await _analysis_stream.create(
        (user_id, code),
        runner,
        error_handler=log_error,
    )
