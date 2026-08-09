"""量化回测持久化任务 Worker。"""

import asyncio
import logging

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.modules.quant.persistence import runs as run_store
from app.modules.quant.schemas import QuantBacktestCreate
from app.modules.quant.service import execute_backtest
from app.runtime.task_health import background_task_health, new_task_health
from app.runtime.task_scheduler import BACKGROUND_TASK_OWNER_ID

logger = logging.getLogger(__name__)

QUANT_JOB_OWNER_ID = f"{BACKGROUND_TASK_OWNER_ID}:quant"
QUANT_JOB_HEALTH_NAME = "quant_job_worker"


async def process_next_quant_job(owner_id: str = QUANT_JOB_OWNER_ID) -> bool:
    job = await call_blocking(
        run_store.claim_next,
        owner_id,
        lease_seconds=600,
        semaphore=database_semaphore,
    )
    if job is None:
        return False
    try:
        request = QuantBacktestCreate.model_validate(job.request)
        result, input_snapshot = await execute_backtest(request)
        completed = await call_blocking(
            run_store.complete,
            job.id,
            owner_id,
            result,
            input_snapshot,
            semaphore=database_semaphore,
        )
        if not completed:
            logger.info("量化任务已取消或租约失效，丢弃结果: run_id=%s", job.id)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.exception("量化回测执行失败: run_id=%s", job.id)
        await call_blocking(
            run_store.fail,
            job.id,
            owner_id,
            str(error),
            semaphore=database_semaphore,
        )
    return True


async def run_quant_job_worker() -> None:
    health = background_task_health.setdefault(QUANT_JOB_HEALTH_NAME, new_task_health())
    health["status"] = "running"
    try:
        while True:
            try:
                processed = await process_next_quant_job()
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
