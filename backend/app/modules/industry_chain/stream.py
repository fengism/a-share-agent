"""产业链分析 SSE 任务适配。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from app.modules.workflow.public import (
    create_workflow_event_generator,
    submit_industry_chain_workflow,
)


async def create_industry_chain_event_generator(name: str, user_id: int) -> AsyncGenerator[dict, None]:
    """创建指定产业链的 SSE 事件生成器。"""
    submission = await submit_industry_chain_workflow(name, user_id)
    stream = await create_workflow_event_generator(submission.job.id, user_id)
    if stream is None:
        raise RuntimeError("Workflow 提交后无法读取")
    return stream
