"""已领取 Bot 任务的业务执行与响应投递。"""

from __future__ import annotations

import logging
from dataclasses import asdict

from app.core.concurrency.rate_limiter import database_semaphore
from app.core.metrics import metrics
from app.modules.bot.models import BotMessage, BotResponse
from app.modules.bot.persistence import jobs as job_store
from app.modules.bot.persistence.jobs import BotJob
from app.modules.bot.platforms.base import BotPlatform
from app.modules.bot.service import BotService

logger = logging.getLogger(__name__)
_PROGRESS_COMMANDS = frozenset({"analyze", "market", "batch"})


async def execute_bot_job(
    job: BotJob,
    owner_id: str,
    message: BotMessage,
    platform: BotPlatform,
    service: BotService,
    *,
    blocking_runner,
) -> None:
    async def report_progress(progress_response: BotResponse) -> None:
        try:
            await platform.send_response(message, progress_response)
        except Exception:
            metrics.record_bot_event("progress_send_failed")
            logger.exception(
                "Bot 任务进度回发失败: job_id=%s event_id=%s",
                job.id,
                job.event_id,
            )

    if job.response_payload is None:
        if job.command_name in _PROGRESS_COMMANDS:
            await report_progress(
                BotResponse(
                    text=(
                        f"任务 `{job.id[:8]}` 已开始执行。\n"
                        f"可发送 `/task {job.id[:8]}` 查询状态。"
                    ),
                    title="任务已受理",
                )
            )
        response = await service.dispatch(
            message,
            job_id=job.id,
            progress_reporter=report_progress,
        )
        if response is None:
            completed = await blocking_runner(
                job_store.complete,
                job.id,
                owner_id,
                semaphore=database_semaphore,
            )
            if not completed:
                raise RuntimeError("Bot 空响应任务完成状态更新失败")
            metrics.record_bot_event("succeeded")
            return
        saved = await blocking_runner(
            job_store.save_response,
            job.id,
            owner_id,
            asdict(response),
            semaphore=database_semaphore,
        )
        if not saved:
            raise RuntimeError("Bot 任务响应持久化失败")
    else:
        response = BotResponse(**job.response_payload)

    try:
        await platform.send_response(message, response)
    except Exception:
        metrics.record_bot_event("response_send_failed")
        raise
    completed = await blocking_runner(
        job_store.complete,
        job.id,
        owner_id,
        semaphore=database_semaphore,
    )
    if not completed:
        raise RuntimeError("Bot 任务完成状态更新失败")
    metrics.record_bot_event("succeeded")


__all__ = ["execute_bot_job"]
