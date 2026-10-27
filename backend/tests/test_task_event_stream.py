"""按业务键的后台任务 + SSE 事件流（``KeyedTaskEventStream``）。

这份实现同时承担三件事：同键去重、事件序列化、断流时取消后台任务。此前覆盖率是 0%，
而它的失效方式都是"用户侧的症状"：重复点两次出现两份任务、关掉页面后台还在跑、
任务抛错后流永远不结束。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core.concurrency.task_stream import KeyedTaskEventStream

pytestmark = pytest.mark.anyio


class _Event:
    def __init__(self, type_: str, payload: dict) -> None:
        self.type = type_
        self._payload = payload

    def model_dump(self) -> dict:
        return self._payload


class _Duplicate(Exception):
    pass


def _stream(keepalive: float = 5.0) -> KeyedTaskEventStream[_Event]:
    return KeyedTaskEventStream(lambda: _Duplicate("duplicate"), keepalive_seconds=keepalive)


async def _collect(generator, limit: int | None = None) -> list[dict]:
    frames: list[dict] = []
    async for frame in generator:
        frames.append(frame)
        if limit is not None and len(frames) >= limit:
            break
    return frames


async def test_events_are_serialized_as_sse_frames() -> None:
    stream = _stream()

    async def runner(emit) -> None:
        await emit(_Event("progress", {"step": 1, "名称": "采集"}))
        await emit(_Event("done", {"ok": True}))

    frames = await _collect(await stream.create("k", runner))
    assert [frame["event"] for frame in frames] == ["progress", "done"]
    assert json.loads(frames[0]["data"]) == {"step": 1, "名称": "采集"}
    assert stream.active_tasks == {}


async def test_duplicate_key_while_running_is_rejected() -> None:
    stream = _stream()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_runner(emit) -> None:
        started.set()
        await release.wait()
        await emit(_Event("done", {}))

    generator = await stream.create("same", slow_runner)
    await started.wait()

    with pytest.raises(_Duplicate):
        await stream.create("same", lambda emit: asyncio.sleep(0))
    # 被拒绝的第二次调用不能污染注册表
    assert list(stream.active_tasks) == ["same"]

    release.set()
    await _collect(generator)
    assert stream.active_tasks == {}


async def test_key_can_be_reused_after_completion() -> None:
    stream = _stream()

    async def runner(emit) -> None:
        await emit(_Event("done", {}))

    await _collect(await stream.create("k", runner))
    await _collect(await stream.create("k", runner))
    assert stream.active_tasks == {}


async def test_error_handler_receives_runner_exception_and_stream_ends() -> None:
    stream = _stream()
    seen: list[str] = []

    async def failing(emit) -> None:
        await emit(_Event("progress", {}))
        raise RuntimeError("boom")

    frames = await _collect(
        await stream.create("k", failing, error_handler=lambda error: seen.append(type(error).__name__)),
    )
    assert [frame["event"] for frame in frames] == ["progress"]
    assert seen == ["RuntimeError"]
    assert stream.active_tasks == {}


async def test_keepalive_comment_is_emitted_when_idle() -> None:
    stream = _stream(keepalive=0.01)
    release = asyncio.Event()

    async def idle(emit) -> None:
        await release.wait()

    generator = await stream.create("k", idle)
    first = await asyncio.wait_for(anext(generator), timeout=2.0)
    assert first == {"comment": "keepalive"}
    release.set()
    await generator.aclose()
    assert stream.active_tasks == {}


async def test_closing_the_generator_cancels_the_background_task() -> None:
    stream = _stream()
    cancelled = asyncio.Event()

    async def forever(emit) -> None:
        try:
            await emit(_Event("progress", {}))
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    generator = await stream.create("k", forever)
    frame = await asyncio.wait_for(anext(generator), timeout=2.0)
    assert frame["event"] == "progress"
    # 用户关掉页面 → 生成器被关闭 → 后台任务必须随之取消（否则继续烧数据源额度）
    await generator.aclose()
    assert cancelled.is_set()
    assert stream.active_tasks == {}


async def test_never_started_generator_does_not_leave_a_stale_entry() -> None:
    """未消费就丢弃的流不应在注册表里留下活跃键（任务自行结束时会注销）。"""
    stream = _stream()

    async def quick(emit) -> None:
        await emit(_Event("done", {}))

    generator = await stream.create("k", quick)
    await generator.aclose()
    # 让后台任务跑完并执行 finally 注销
    for _ in range(50):
        if not stream.active_tasks:
            break
        await asyncio.sleep(0.01)
    assert stream.active_tasks == {}
