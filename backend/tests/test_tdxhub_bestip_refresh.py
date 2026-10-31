"""TDX 最优服务器刷新任务：两个共享实例各自冷却时的重置行为。"""

import pytest

from app.infrastructure.providers import tdxhub as tdxhub_module
from app.runtime import background_tasks


class _StubShared:
    def __init__(self, cooling: bool) -> None:
        self.cooling = cooling
        self.resets = 0

    def is_cooling_down(self) -> bool:
        return self.cooling

    def cooldown_remaining_seconds(self) -> float:
        return 12.3

    def reset(self) -> None:
        self.resets += 1


async def _run_iteration(monkeypatch, lenient: _StubShared, strict: _StubShared):
    captured = {}

    async def fake_run_periodic(**kwargs):
        captured["factory"] = kwargs["coro_factory"]

    monkeypatch.setattr(background_tasks.task_scheduler, "run_periodic", fake_run_periodic)
    monkeypatch.setattr(tdxhub_module, "shared_tdxhub_quotes", lenient)
    monkeypatch.setattr(tdxhub_module, "shared_tdxhub_raise_quotes", strict)

    import sys

    import tdxhub.config as tdxhub_config

    server_module = sys.modules["tdxhub.server"]
    monkeypatch.setattr(
        server_module,
        "server",
        lambda **kwargs: [("10.0.0.9", 7709), ("10.0.0.8", 7709)],
    )
    monkeypatch.setattr(tdxhub_config, "update", lambda payload: captured.setdefault("update", payload))

    await background_tasks.refresh_tdxhub_best_ip()
    await captured["factory"]()
    return captured


@pytest.mark.asyncio
async def test_refresh_skips_both_instances_while_cooling_down(monkeypatch):
    lenient = _StubShared(cooling=True)
    strict = _StubShared(cooling=True)

    captured = await _run_iteration(monkeypatch, lenient, strict)

    assert lenient.resets == 0
    assert strict.resets == 0
    # 即使不重置客户端，最优服务器仍要写回内存配置
    assert captured["update"] == {"BESTIP": {"HQ": ("10.0.0.9", 7709)}}


@pytest.mark.asyncio
async def test_refresh_resets_only_instance_that_is_not_cooling(monkeypatch):
    lenient = _StubShared(cooling=False)
    strict = _StubShared(cooling=True)

    await _run_iteration(monkeypatch, lenient, strict)

    assert lenient.resets == 1
    assert strict.resets == 0
