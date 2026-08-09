"""产业链分析 SSE 任务适配。"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from app.core.concurrency.task_stream import KeyedTaskEventStream
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.pipeline import run_industry_chain_analysis

logger = logging.getLogger(__name__)


class IndustryChainAlreadyRunningError(RuntimeError):
    """同一用户的同名产业链已有分析任务在运行。"""


_industry_chain_stream = KeyedTaskEventStream[IndustryChainProgress](
    lambda: IndustryChainAlreadyRunningError("该产业链正在分析中，请稍后")
)
_active_industry_chains = _industry_chain_stream.active_tasks


def task_key(user_id: int, name: str) -> tuple[int, str]:
    return user_id, name


async def create_industry_chain_event_generator(name: str, user_id: int) -> AsyncGenerator[dict, None]:
    """创建指定产业链的 SSE 事件生成器。"""

    async def runner(progress_callback) -> None:
        await run_industry_chain_analysis(name, user_id, progress_callback=progress_callback)

    def log_error(error: Exception) -> None:
        logger.warning("产业链分析后台任务异常退出: %s, error=%s", name, error)

    return await _industry_chain_stream.create(
        task_key(user_id, name),
        runner,
        error_handler=log_error,
    )
