import asyncio
import logging

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence import task_lease_store

logger = logging.getLogger(__name__)


class TaskLeaderLease:
    def __init__(self, task_name: str, owner_id: str, lease_seconds: float) -> None:
        self.task_name = task_name
        self.owner_id = owner_id
        self.lease_seconds = max(1.0, lease_seconds)
        self._held = False
        self._lost = asyncio.Event()
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    async def try_acquire(self) -> bool:
        if self._held and not self.lost:
            return True
        if self._held:
            await self.close()
        acquired = await call_blocking(
            task_lease_store.acquire_task_lease,
            self.task_name,
            self.owner_id,
            self.lease_seconds,
            semaphore=database_semaphore,
        )
        if not acquired:
            return False
        self._held = True
        self._lost = asyncio.Event()
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat(),
            name=f"{self.task_name}_lease_heartbeat",
        )
        logger.info("后台任务取得主节点租约 task=%s owner=%s", self.task_name, self.owner_id)
        return True

    async def wait(self, delay_seconds: float) -> bool:
        if not self._held:
            await asyncio.sleep(delay_seconds)
            return True
        try:
            await asyncio.wait_for(self._lost.wait(), timeout=delay_seconds)
        except TimeoutError:
            return True
        return False

    async def close(self) -> None:
        heartbeat = self._heartbeat_task
        self._heartbeat_task = None
        if heartbeat is not None:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
        if self._held:
            try:
                await call_blocking(
                    task_lease_store.release_task_lease,
                    self.task_name,
                    self.owner_id,
                    semaphore=database_semaphore,
                )
            except Exception:
                logger.warning("释放后台任务租约失败 task=%s", self.task_name, exc_info=True)
        self._held = False

    async def _heartbeat(self) -> None:
        interval = max(0.1, self.lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            try:
                renewed = await call_blocking(
                    task_lease_store.renew_task_lease,
                    self.task_name,
                    self.owner_id,
                    self.lease_seconds,
                    semaphore=database_semaphore,
                )
            except Exception:
                logger.error("续租后台任务主节点失败 task=%s", self.task_name, exc_info=True)
                renewed = False
            if not renewed:
                self._lost.set()
                logger.warning("后台任务主节点租约已丢失 task=%s", self.task_name)
                return
