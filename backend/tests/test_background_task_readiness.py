"""后台任务就绪探测语义。

`readiness_required=True` 的任务一旦不健康，`/api/health/ready` 会返回 503，
Docker healthcheck 据此把容器判为不健康。因此「什么算不健康」必须精确：

- 真故障（崩溃、连续失败、反复重启）→ 503，让编排层摘流量；
- 预期状态（配置停用、正常关闭、未在本副本启动、standby、重启中）→ 200，
  否则一次正常配置变更就能把整个服务判死。
"""

from __future__ import annotations

import asyncio

import pytest

from app.runtime import health as health_module
from app.runtime import task_health as task_health_module
from app.runtime.task_health import (
    background_task_health,
    mark_task_cancelled,
    mark_task_disabled_by_config,
    new_task_health,
    register_background_task,
    task_snapshot,
)

_WORKER = "quant_job_worker"


@pytest.fixture(autouse=True)
def _isolated_health() -> None:
    background_task_health.clear()
    task_health_module._critical_background_tasks.clear()
    task_health_module._readiness_background_tasks.clear()
    yield
    background_task_health.clear()
    task_health_module._critical_background_tasks.clear()
    task_health_module._readiness_background_tasks.clear()


def _readiness_status_code() -> int:
    def db_ok() -> bool:
        return True

    def encryption_ok() -> str:
        return "ok"

    response = asyncio.run(
        health_module.readiness_response(
            database_check=db_ok,
            encryption_check=encryption_ok,
            background_snapshot=lambda: dict(background_task_health),
        )
    )
    return response.status_code


def _healthy_entry(status: str = "running") -> dict:
    entry = register_background_task(
        _WORKER,
        critical=True,
        readiness_required=True,
    )
    entry["status"] = status
    return entry


def test_running_readiness_task_keeps_service_ready() -> None:
    _healthy_entry("running")
    assert _readiness_status_code() == 200


def test_consecutive_failures_make_service_unready() -> None:
    entry = _healthy_entry("error")
    entry["consecutive_errors"] = 5
    assert _readiness_status_code() == 503


def test_unexpected_exit_makes_service_unready() -> None:
    entry = _healthy_entry("error")
    entry["unexpected_exit"] = True
    assert _readiness_status_code() == 503


def test_repeated_restarts_make_service_unready() -> None:
    entry = _healthy_entry("starting")
    entry["consecutive_restarts"] = 5
    assert _readiness_status_code() == 503


def test_config_disabled_task_does_not_break_readiness() -> None:
    """bot_enabled 之类开关把任务停掉时，服务本身仍然健康。"""
    _healthy_entry("running")
    mark_task_disabled_by_config(_WORKER)
    assert _readiness_status_code() == 200


def test_clean_cancellation_does_not_break_readiness() -> None:
    """应用正常关闭时任务被 cancel，不应被报成故障。"""
    _healthy_entry("running")
    mark_task_cancelled(_WORKER)
    assert _readiness_status_code() == 200


def test_unknown_task_is_not_treated_as_failure() -> None:
    """任务在本副本从未启动（初始禁用 / 非主节点）时，登记表里没有记录。"""
    background_task_health.clear()
    task_health_module._readiness_background_tasks.add(_WORKER)
    assert _readiness_status_code() == 200


def test_standby_replica_stays_ready() -> None:
    """非主节点副本不执行周期任务，但服务可用。"""
    entry = _healthy_entry("standby")
    entry["role"] = "standby"
    assert _readiness_status_code() == 200


def test_disabled_flag_takes_precedence_over_stopped_status() -> None:
    """两种停止都写 status=stopped，靠标记区分，不能再靠状态字符串猜。"""
    entry = _healthy_entry("running")
    mark_task_disabled_by_config(_WORKER)
    assert entry["status"] == "stopped"
    assert _readiness_status_code() == 200

    # 同样 status=stopped，但属于崩溃 → 不健康
    crashed = _healthy_entry("running")
    crashed["status"] = "stopped"
    crashed["unexpected_exit"] = True
    assert _readiness_status_code() == 503


def test_re_registration_clears_cancel_and_disable_markers() -> None:
    """任务被重新启用时会重新注册，旧的停止原因必须清掉。"""
    entry = _healthy_entry("running")
    mark_task_cancelled(_WORKER)
    assert entry["cancelled_cleanly"] is True

    re_registered = register_background_task(
        _WORKER,
        critical=True,
        readiness_required=True,
    )
    assert re_registered["cancelled_cleanly"] is False
    assert re_registered["disabled_by_config"] is False
    assert re_registered["unexpected_exit"] is False


def test_snapshot_exposes_stop_reason() -> None:
    entry = _healthy_entry("running")
    mark_task_disabled_by_config(_WORKER)
    snapshot = task_snapshot()[_WORKER]
    assert snapshot["disabled_by_config"] is True
    assert snapshot["cancelled_cleanly"] is False
    assert entry["status"] == "stopped"


def test_new_task_health_reports_no_stop_reason_initially() -> None:
    entry = new_task_health()
    assert entry["disabled_by_config"] is False
    assert entry["cancelled_cleanly"] is False


# --- Worker 槽位循环的健康上报 -------------------------------------------------
#
# 回归背景：三个 job worker 的槽位循环是 `except Exception: continue`（故意不退出，
# 靠上层 reconcile 兜底）。若不显式累加 consecutive_errors，一个每轮都失败的
# Worker 与正常 Worker 在健康快照里完全一样，readiness 会一直返回 200——接线
# readiness 等于白接。这几个用例锁住「计数必须真的动」。


def test_slot_failure_increments_consecutive_errors() -> None:
    from app.runtime.job_workers import _record_slot_failure

    _record_slot_failure("quant_job_worker", "RuntimeError")
    entry = background_task_health["quant_job_worker"]
    assert entry["consecutive_errors"] == 1
    assert entry["status"] == "error"
    assert entry["last_error"] == "RuntimeError"

    _record_slot_failure("quant_job_worker", "RuntimeError")
    assert entry["consecutive_errors"] == 2


def test_slot_success_resets_failure_streak() -> None:
    from app.runtime.job_workers import _record_slot_failure, _record_slot_success

    for _ in range(3):
        _record_slot_failure("quant_job_worker", "RuntimeError")
    entry = background_task_health["quant_job_worker"]
    assert entry["consecutive_errors"] == 3

    _record_slot_success("quant_job_worker")
    assert entry["consecutive_errors"] == 0
    assert entry["status"] == "running"
    assert entry["last_error"] is None


def test_slot_failure_clears_stale_clean_cancel_marker() -> None:
    """重新跑起来又失败时，不能还挂着「上次是正常取消」的标记。"""
    from app.runtime.job_workers import _record_slot_failure

    entry = _healthy_entry("running")
    mark_task_cancelled(_WORKER)
    assert entry["cancelled_cleanly"] is True

    _record_slot_failure(_WORKER, "RuntimeError")
    assert entry["cancelled_cleanly"] is False
    assert _readiness_status_code() == 200  # 仅失败 1 次，未达阈值


def test_failure_streak_crosses_readiness_threshold() -> None:
    from app.runtime.job_workers import _record_slot_failure

    _healthy_entry("running")
    assert _readiness_status_code() == 200

    for _ in range(2):  # 阈值默认 3，前两次不应摘流量
        _record_slot_failure(_WORKER, "RuntimeError")
        assert _readiness_status_code() == 200

    _record_slot_failure(_WORKER, "RuntimeError")
    assert _readiness_status_code() == 503


# --- bot worker reconcile 不得抹掉槽位上报的失败计数 ----------------------------
#
# 回归背景：run_bot_job_worker 的 reconcile 循环里曾有一段
# `elif health["status"] == "error": health["consecutive_errors"] = 0`。
# 槽位循环是 catch-all 且正常情况下从不退出，所以每轮 reconcile 都走这个 elif，
# 把槽位刚写入的失败计数清零——bot worker 每轮都失败，健康快照却永远显示
# errors=0 / status=running。


async def _run_bot_worker_briefly(monkeypatch, *, failing: bool, seconds: float = 2.5):
    import types

    import app.runtime.job_workers as job_workers

    fake_settings = types.SimpleNamespace(
        bot_enabled=True,
        bot_job_poll_seconds=0.2,
        bot_job_worker_concurrency=1,
    )
    monkeypatch.setattr(job_workers, "get_settings", lambda: fake_settings)

    async def fake_process(owner_id, settings_provider):
        if failing:
            raise RuntimeError("上游挂了")
        return False

    monkeypatch.setattr(job_workers, "process_next_bot_job", fake_process)
    task = asyncio.create_task(job_workers.run_bot_job_worker())
    try:
        await asyncio.sleep(seconds)
        return dict(background_task_health.get("bot_job_worker", {}))
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_bot_worker_failures_are_not_erased_by_reconcile(monkeypatch) -> None:
    register_background_task("bot_job_worker", critical=True, readiness_required=False)
    health = asyncio.run(_run_bot_worker_briefly(monkeypatch, failing=True))
    assert health["consecutive_errors"] > 0, "槽位失败没被记下来（reconcile 把计数抹掉了）"
    assert health["status"] == "error"
    assert health["last_error"] == "RuntimeError"


def test_bot_worker_success_keeps_counter_clear(monkeypatch) -> None:
    register_background_task("bot_job_worker", critical=True, readiness_required=False)
    health = asyncio.run(_run_bot_worker_briefly(monkeypatch, failing=False))
    assert health["consecutive_errors"] == 0
    assert health["status"] == "running"


def test_slot_failure_backoff_slows_repeated_failures() -> None:
    """失败要退避，否则上游抖动几秒就能把计数推过阈值。"""
    from app.runtime.job_workers import IdlePollBackoff

    backoff = IdlePollBackoff()
    delays = [backoff.next_delay(0.1) for _ in range(6)]
    assert delays == sorted(delays), "退避序列必须单调不减"
    assert delays[0] < delays[-1]
    assert delays[-1] <= IdlePollBackoff().max_seconds


def test_snapshot_exposes_critical_and_readiness_separately() -> None:
    """快照必须把两个标志分开导出。

    历史上 ``critical`` 只是个没有消费方的标记：快照和指标里都没有它，
    运维无法回答「这个任务挂了要紧吗」。而 ``critical`` 与
    ``readiness_required`` 表达的是两种独立动作（告警 / 摘流量），
    不能用其中一个冒充另一个。
    """
    register_background_task("quant_job_worker", critical=True, readiness_required=True)
    register_background_task("wal_checkpoint", critical=True, readiness_required=False)
    register_background_task("macro_analysis_prewarm", critical=False, readiness_required=False)

    snapshot = task_snapshot()
    assert snapshot["quant_job_worker"]["critical"] is True
    assert snapshot["quant_job_worker"]["readiness_required"] is True
    assert snapshot["wal_checkpoint"]["critical"] is True
    assert snapshot["wal_checkpoint"]["readiness_required"] is False
    assert snapshot["macro_analysis_prewarm"]["critical"] is False
    assert snapshot["macro_analysis_prewarm"]["readiness_required"] is False


def test_critical_flag_does_not_drag_readiness_down() -> None:
    """critical=True 但 readiness_required=False 的任务挂掉时，仍应 200。

    备份/预热抖动不该把全部流量摘掉——这是当初引入两个字段的原因。
    """
    register_background_task("wal_checkpoint", critical=True, readiness_required=False)
    background_task_health["wal_checkpoint"].update(
        {"status": "error", "unexpected_exit": True, "consecutive_errors": 10}
    )
    assert _readiness_status_code() == 200
