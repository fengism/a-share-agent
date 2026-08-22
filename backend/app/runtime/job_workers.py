"""持久化业务任务的 Runtime 轮询与健康管理。"""

import asyncio
import logging

from app.configuration import get_settings
from app.modules.bot.public import process_next_bot_job
from app.modules.quant.public import process_next_quant_job
from app.runtime.task_health import background_task_health, new_task_health
from app.runtime.task_scheduler import BACKGROUND_TASK_OWNER_ID
from app.runtime.workflow_worker import process_next_workflow_job

logger = logging.getLogger(__name__)

BOT_JOB_OWNER_ID = f"{BACKGROUND_TASK_OWNER_ID}:bot"
BOT_JOB_HEALTH_NAME = "bot_job_worker"
QUANT_JOB_OWNER_ID = f"{BACKGROUND_TASK_OWNER_ID}:quant"
QUANT_JOB_HEALTH_NAME = "quant_job_worker"
WORKFLOW_JOB_OWNER_ID = f"{BACKGROUND_TASK_OWNER_ID}:workflow"
WORKFLOW_JOB_HEALTH_NAME = "workflow_job_worker"
_BOT_RECONCILE_INTERVAL_SECONDS = 1.0


async def _run_bot_job_worker_slot(owner_id: str) -> None:
    while True:
        settings = get_settings()
        if not settings.bot_enabled:
            await asyncio.sleep(max(0.1, settings.bot_job_poll_seconds))
            continue
        try:
            processed = await process_next_bot_job(
                owner_id=owner_id,
                settings_provider=lambda: settings,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Bot Worker 轮询失败")
            processed = False
        if not processed:
            await asyncio.sleep(max(0.1, settings.bot_job_poll_seconds))


async def run_bot_job_worker() -> None:
    workers: dict[int, asyncio.Task[None]] = {}
    reported_concurrency = None
    health = background_task_health.setdefault(BOT_JOB_HEALTH_NAME, new_task_health())
    health["status"] = "running"
    try:
        while True:
            concurrency = min(8, max(1, get_settings().bot_job_worker_concurrency))

            completed = [index for index, task in workers.items() if task.done()]
            completed_tasks = [workers.pop(index) for index in completed]
            completed_results = (
                await asyncio.gather(*completed_tasks, return_exceptions=True) if completed_tasks else []
            )
            if completed_results:
                health["status"] = "error"
                health["consecutive_errors"] += len(completed_results)
                for index, result in zip(completed, completed_results):
                    if isinstance(result, asyncio.CancelledError):
                        error_type = "CancelledError"
                        logger.error("Bot Worker 槽位意外取消，将自动重启: slot=%s", index)
                    elif isinstance(result, BaseException):
                        error_type = type(result).__name__
                        logger.error(
                            "Bot Worker 槽位异常退出，将自动重启: slot=%s error_type=%s",
                            index,
                            error_type,
                            exc_info=(type(result), result, result.__traceback__),
                        )
                    else:
                        error_type = "UnexpectedExit"
                        logger.error("Bot Worker 槽位意外结束，将自动重启: slot=%s", index)
                    health["last_error"] = error_type
            elif health["status"] == "error":
                health["status"] = "running"
                health["last_error"] = None
                health["consecutive_errors"] = 0

            removed = [index for index in workers if index > concurrency]
            removed_tasks = [workers.pop(index) for index in removed]
            for task in removed_tasks:
                task.cancel()
            if removed_tasks:
                await asyncio.gather(*removed_tasks, return_exceptions=True)

            for index in range(1, concurrency + 1):
                if index in workers:
                    continue
                owner_id = f"{BOT_JOB_OWNER_ID}:{index}"
                workers[index] = asyncio.create_task(
                    _run_bot_job_worker_slot(owner_id),
                    name=f"bot_job_worker:{index}",
                )

            if concurrency != reported_concurrency:
                logger.info(
                    "Bot 持久化任务 Worker 并发已调整: owner=%s concurrency=%s",
                    BOT_JOB_OWNER_ID,
                    concurrency,
                )
                reported_concurrency = concurrency

            await asyncio.sleep(_BOT_RECONCILE_INTERVAL_SECONDS)
    finally:
        for task in workers.values():
            task.cancel()
        if workers:
            await asyncio.gather(*workers.values(), return_exceptions=True)
        health["status"] = "stopped"


async def run_quant_job_worker() -> None:
    health = background_task_health.setdefault(QUANT_JOB_HEALTH_NAME, new_task_health())
    health["status"] = "running"
    try:
        while True:
            try:
                processed = await process_next_quant_job(QUANT_JOB_OWNER_ID)
            except Exception as error:
                logger.exception("量化 Worker 轮询失败")
                health["status"] = "error"
                health["last_error"] = type(error).__name__
                await asyncio.sleep(1)
                continue
            health["status"] = "running"
            health["last_error"] = None
            if not processed:
                await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        health["status"] = "stopped"
        raise
    except Exception as error:
        health["status"] = "error"
        health["last_error"] = type(error).__name__
        raise


async def _run_workflow_job_worker_slot(owner_id: str) -> None:
    while True:
        try:
            processed = await process_next_workflow_job(owner_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Workflow Worker 槽位轮询失败: owner=%s", owner_id)
            await asyncio.sleep(1)
            continue
        if not processed:
            await asyncio.sleep(get_settings().workflow_job_poll_seconds)


async def run_workflow_job_worker() -> None:
    workers: dict[int, asyncio.Task[None]] = {}
    health = background_task_health.setdefault(WORKFLOW_JOB_HEALTH_NAME, new_task_health())
    health["status"] = "running"
    try:
        while True:
            concurrency = get_settings().workflow_job_worker_concurrency
            removed = [index for index in workers if index > concurrency]
            removed_tasks = [workers.pop(index) for index in removed]
            for task in removed_tasks:
                task.cancel()
            if removed_tasks:
                await asyncio.gather(*removed_tasks, return_exceptions=True)

            for index in range(1, concurrency + 1):
                if index not in workers:
                    workers[index] = asyncio.create_task(
                        _run_workflow_job_worker_slot(f"{WORKFLOW_JOB_OWNER_ID}:{index}"),
                        name=f"workflow_job_worker:{index}",
                    )
            health["status"] = "running"
            health["last_error"] = None
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        health["status"] = "stopped"
        raise
    except Exception as error:
        health["status"] = "error"
        health["last_error"] = type(error).__name__
        raise
    finally:
        for task in workers.values():
            task.cancel()
        if workers:
            await asyncio.gather(*workers.values(), return_exceptions=True)
