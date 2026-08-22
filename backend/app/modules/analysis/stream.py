"""个股分析 SSE 任务适配。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from app.modules.workflow.public import (
    create_workflow_event_generator,
    submit_analysis_workflow,
)


async def create_analysis_event_generator(code: str, user_id: int) -> AsyncGenerator[dict, None]:
    """创建指定股票的 SSE 事件生成器。"""
    submission = await submit_analysis_workflow(code, user_id)
    stream = await create_workflow_event_generator(submission.job.id, user_id)
    if stream is None:
        raise RuntimeError("Workflow 提交后无法读取")
    return stream
