"""支持重试、健康状态和主节点选举的后台任务调度器。"""

import asyncio
import logging
import os
import random
import socket
import time
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from app.configuration import get_settings
from app.domain.timezones import market_now
from app.infrastructure.persistence.task_leader import TaskLeaderLease
from app.runtime.task_health import background_task_health, new_task_health

logger = logging.getLogger(__name__)

BACKGROUND_TASK_OWNER_ID = os.environ.get("INSTANCE_ID") or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"


@dataclass(slots=True)
class _PeriodicState:
    name: str
    entry: dict
    retry_base_seconds: float
    loop_count: int = 0
    consecutive_errors: int = 0

    def schedule(self, delay: float) -> None:
        self.entry["next_run"] = (
            market_now() + timedelta(seconds=delay)
        ).isoformat()

    def record_error(self, error: Exception, duration_ms: float | None = None) -> float:
        self.consecutive_errors += 1
        self.entry["status"] = "error"
        self.entry["last_error"] = type(error).__name__
        self.entry["consecutive_errors"] = self.consecutive_errors
        if duration_ms is not None:
            self.entry["last_duration_ms"] = duration_ms
        return float(min(
            600.0,
            self.retry_base_seconds * (2 ** (self.consecutive_errors - 1)),
        ))

    def record_success(self, duration_ms: float) -> None:
        self.entry["last_duration_ms"] = duration_ms
        self.entry["last_run"] = market_now().isoformat()
        self.entry["last_error"] = None
        self.entry["consecutive_errors"] = 0
        self.consecutive_errors = 0


@dataclass(frozen=True, slots=True)
class _IterationResult:
    completed: bool
    delay: float = 0.0


async def _wait_initial_jitter(state: _PeriodicState, delay: float) -> None:
    if delay <= 0:
        return
    state.entry["status"] = "scheduled"
    state.schedule(delay)
    await asyncio.sleep(delay)


async def _acquire_leadership(
    state: _PeriodicState,
    leader_lease,
    standby_delay: float,
) -> bool:
    try:
        is_leader = await leader_lease.try_acquire()
    except Exception as exc:
        delay = state.record_error(exc)
        state.schedule(delay)
        await asyncio.sleep(delay)
        return False
    if not is_leader:
        state.entry["status"] = "standby"
        state.entry["role"] = "standby"
        delay = max(0.0, standby_delay)
        state.schedule(delay)
        await asyncio.sleep(delay)
        return False
    state.entry["role"] = "leader"
    return True


async def _run_iteration(
    state: _PeriodicState,
    coro_factory,
    health_check,
    interval_seconds: float | None,
    leader_lease,
) -> _IterationResult:
    state.loop_count += 1
    state.entry["status"] = "running"
    state.entry["next_run"] = None
    started_at = time.perf_counter()
    try:
        if health_check is not None and not await health_check():
            raise RuntimeError(f"后台任务 [{state.name}] 健康检查失败")
        await coro_factory()
        if leader_lease is not None and leader_lease.lost:
            raise RuntimeError(f"后台任务 [{state.name}] 主节点租约已丢失")
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        delay = state.record_error(exc, duration_ms)
        logger.error(
            "后台任务 [%s] 第 %s 次循环失败（连续 %s 次）: %s",
            state.name,
            state.loop_count,
            state.consecutive_errors,
            exc,
            exc_info=True,
        )
        return _IterationResult(completed=False, delay=delay)

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    state.record_success(duration_ms)
    if interval_seconds is None:
        state.entry["status"] = "completed"
        state.entry["next_run"] = None
        return _IterationResult(completed=True)
    state.entry["status"] = "sleeping"
    return _IterationResult(completed=False, delay=max(0.0, interval_seconds))


async def _wait_for_next_run(
    state: _PeriodicState,
    leader_lease,
    delay: float,
) -> None:
    state.schedule(delay)
    if leader_lease is None:
        await asyncio.sleep(delay)
        return
    if not await leader_lease.wait(delay):
        state.entry["status"] = "standby"
        state.entry["role"] = "standby"
        state.entry["next_run"] = None


async def run_periodic(
    name: str,
    coro_factory,
    interval_seconds: float | None,
    health_check=None,
    *,
    initial_jitter_seconds: float | None = None,
    retry_base_seconds: float = 2.0,
    leader_election: bool = False,
    lease_seconds: float | None = None,
    standby_poll_seconds: float | None = None,
    lease_factory=TaskLeaderLease,
    settings_provider=get_settings,
    owner_id: str = BACKGROUND_TASK_OWNER_ID,
):
    """运行可恢复、可选主并带健康状态的后台任务循环。"""
    entry = background_task_health.setdefault(name, new_task_health())
    state = _PeriodicState(name, entry, retry_base_seconds)
    jitter_limit = (
        settings_provider().background_task_jitter_seconds
        if initial_jitter_seconds is None
        else initial_jitter_seconds
    )
    initial_delay = random.uniform(0, max(0.0, jitter_limit))
    leader_lease = None
    standby_delay = 0.0
    if leader_election:
        settings = settings_provider()
        leader_lease = lease_factory(
            name,
            owner_id,
            lease_seconds or settings.background_task_lease_seconds,
        )
        standby_delay = (
            settings.background_task_standby_poll_seconds
            if standby_poll_seconds is None
            else standby_poll_seconds
        )
        entry["role"] = "standby"
    try:
        await _wait_initial_jitter(state, initial_delay)

        while True:
            if leader_lease is not None and not await _acquire_leadership(
                state,
                leader_lease,
                standby_delay,
            ):
                continue

            result = await _run_iteration(
                state,
                coro_factory,
                health_check,
                interval_seconds,
                leader_lease,
            )
            if result.completed:
                return
            await _wait_for_next_run(state, leader_lease, result.delay)
    except asyncio.CancelledError:
        entry["status"] = "stopped"
        entry["next_run"] = None
        raise
    finally:
        if leader_lease is not None:
            await leader_lease.close()


async def run_supervised_once(name: str, coro_factory) -> None:
    await run_periodic(name=name, coro_factory=coro_factory, interval_seconds=None)
