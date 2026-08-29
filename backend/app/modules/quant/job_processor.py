"""量化回测持久化任务的单次处理用例。"""

import asyncio
import logging
from typing import cast

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.modules.quant.persistence import runs as run_store
from app.modules.quant.schemas import QuantBacktestPayload
from app.modules.quant.service import execute_backtest

logger = logging.getLogger(__name__)
QUANT_JOB_LEASE_SECONDS = 600.0
QUANT_JOB_TIMEOUT_SECONDS = 900.0


class QuantLeaseLostError(RuntimeError):
    pass


async def _renew_quant_lease(run_id: str, owner_id: str) -> None:
    interval = min(5.0, max(1.0, QUANT_JOB_LEASE_SECONDS / 3))
    while True:
        await asyncio.sleep(interval)
        renewed = await call_blocking(
            run_store.renew_lease,
            run_id,
            owner_id,
            QUANT_JOB_LEASE_SECONDS,
            semaphore=database_semaphore,
        )
        if not renewed:
            raise QuantLeaseLostError(f"量化任务租约已撤销: run_id={run_id} owner={owner_id}")


async def process_next_quant_job(owner_id: str) -> bool:
    job = await call_blocking(
        run_store.claim_next,
        owner_id,
        lease_seconds=int(QUANT_JOB_LEASE_SECONDS),
        semaphore=database_semaphore,
    )
    if job is None:
        return False

    async def execute() -> tuple[dict, dict]:
        request = QuantBacktestPayload.model_validate(job.request)
        async with asyncio.timeout(QUANT_JOB_TIMEOUT_SECONDS):
            return cast(tuple[dict, dict], await execute_backtest(request))

    execution = asyncio.create_task(execute(), name=f"quant_job_execution:{job.id}")
    heartbeat = asyncio.create_task(
        _renew_quant_lease(job.id, owner_id),
        name=f"quant_job_lease:{job.id}",
    )
    try:
        done, _ = await asyncio.wait(
            {execution, heartbeat},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat in done and execution not in done:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            heartbeat.result()
            raise QuantLeaseLostError(f"量化任务租约任务意外结束: run_id={job.id}")

        result, input_snapshot = await execution
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
    except QuantLeaseLostError as error:
        logger.info("量化任务已停止执行: run_id=%s reason=%s", job.id, error)
    except asyncio.CancelledError:
        execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        cancelled = await call_blocking(
            run_store.cancel_owned,
            job.id,
            owner_id,
            "服务关闭，任务已取消",
            semaphore=database_semaphore,
        )
        if cancelled:
            logger.info("服务关闭，量化任务已取消: run_id=%s", job.id)
        raise
    except TimeoutError:
        status = await call_blocking(
            run_store.fail,
            job.id,
            owner_id,
            "量化回测执行超时",
            semaphore=database_semaphore,
        )
        if status is None:
            logger.info("量化任务租约失效，丢弃超时状态: run_id=%s", job.id)
        else:
            logger.error("量化回测执行超时: run_id=%s timeout=%ss", job.id, QUANT_JOB_TIMEOUT_SECONDS)
    except Exception as error:
        status = await call_blocking(
            run_store.fail,
            job.id,
            owner_id,
            str(error),
            semaphore=database_semaphore,
        )
        if status is None:
            logger.info("量化任务租约失效，丢弃失败状态: run_id=%s", job.id)
        else:
            logger.exception("量化回测执行失败: run_id=%s", job.id)
    finally:
        execution.cancel()
        heartbeat.cancel()
        await asyncio.gather(execution, heartbeat, return_exceptions=True)
    return True
