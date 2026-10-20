"""复盘生成进度：每个阶段都要有 started + completed，采集阶段逐源可见。

此前只有 3 条 `stage_started`，前端进度条永远停在第一步；13 个数据源并发采集时
最慢的那个决定整体等待，期间零可见性。
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from app.core.progress import ProgressEmitter
from app.modules.daily_review import collector, pipeline


async def _zero(*args: object, **kwargs: object) -> list:
    return []


def _patch_sources(monkeypatch: pytest.MonkeyPatch, *, slow: str | None = None) -> None:
    async def _maybe_slow(name: str) -> list:
        if name == slow:
            await asyncio.sleep(0.05)
        return []

    def _source(name: str):
        async def _run(*args: object, **kwargs: object) -> list:
            return await _maybe_slow(name)
        return _run

    for name in (
        "get_indices", "get_hot_stocks", "get_ths_hot_concept", "get_ths_hot_industry",
        "get_dragon_tiger_list", "get_market_statistics", "get_market_news",
        "get_market_volume_stats", "get_macro_data", "get_limit_up_ladder",
    ):
        monkeypatch.setattr(collector, name, _source(name))
    monkeypatch.setattr(collector, "get_macro_analysis", _zero)
    monkeypatch.setattr(collector, "get_limit_break_pool", _zero)
    monkeypatch.setattr(collector, "_target_northbound", _zero)
    monkeypatch.setattr(collector, "search_financial_policy_news", _zero)


# --- 采集阶段逐源进度 ------------------------------------------------------


@pytest.mark.asyncio
async def test_every_source_reports_progress(monkeypatch):
    _patch_sources(monkeypatch)
    events: list[dict] = []

    async def _record(event: dict) -> None:
        events.append(event)

    await collector.collect_daily_review_data(
        date(2026, 10, 15), use_realtime=False, progress_callback=_record,
    )

    assert events, "采集必须上报进度"
    assert all(event["type"] == "source_done" for event in events)
    assert all(event["stage"] == "collect" for event in events)
    total = events[0]["total"]
    assert total == len(events), "每个源恰好上报一次"
    assert [event["done"] for event in events] == list(range(1, total + 1))
    assert {event["status"] for event in events} == {"complete"}


@pytest.mark.asyncio
async def test_failed_source_is_reported_as_unavailable(monkeypatch):
    _patch_sources(monkeypatch)

    async def _boom(*args: object, **kwargs: object) -> list:
        raise RuntimeError("upstream down")

    monkeypatch.setattr(collector, "get_dragon_tiger_list", _boom)
    events: list[dict] = []

    async def _record(event: dict) -> None:
        events.append(event)

    await collector.collect_daily_review_data(
        date(2026, 10, 15), use_realtime=False, progress_callback=_record,
    )

    failed = [event for event in events if event["source"] == "dragon_tiger"]
    assert failed and failed[0]["status"] == "unavailable"
    # 一个源失败不影响其它源继续上报。
    assert len(events) == events[0]["total"]


@pytest.mark.asyncio
async def test_collection_without_callback_is_unchanged(monkeypatch):
    _patch_sources(monkeypatch)

    collection = await collector.collect_daily_review_data(date(2026, 10, 15), use_realtime=False)

    assert collection.values is not None
    assert collection.source_status


# --- 长耗时阶段心跳 --------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_reports_elapsed_time():
    events: list[dict] = []

    async def _record(event: dict) -> None:
        events.append(event)

    progress = ProgressEmitter(_record)
    async with pipeline._stage_heartbeat(
        progress, "analyze", "正在生成", interval=0.01,
    ):
        await asyncio.sleep(0.05)

    beats = [event for event in events if event["type"] == "stage_progress"]
    assert beats, "长耗时阶段必须有心跳"
    assert all(event["stage"] == "analyze" for event in beats)
    assert all("已用" in event["message"] for event in beats)
    assert beats[-1]["elapsed_ms"] > 0


@pytest.mark.asyncio
async def test_heartbeat_stops_after_the_block_and_leaks_no_task():
    events: list[dict] = []

    async def _record(event: dict) -> None:
        events.append(event)

    progress = ProgressEmitter(_record)
    async with pipeline._stage_heartbeat(progress, "analyze", "正在生成", interval=0.01):
        await asyncio.sleep(0.02)
    count = len(events)
    await asyncio.sleep(0.05)

    assert len(events) == count, "离开上下文后不能再有心跳"
    # 没有遗留任务：事件循环里不应有仍挂着的 heartbeat。
    assert not [task for task in asyncio.all_tasks() if not task.done() and task is not asyncio.current_task()]


@pytest.mark.asyncio
async def test_heartbeat_is_a_no_op_without_a_callback():
    progress = ProgressEmitter(None)
    async with pipeline._stage_heartbeat(progress, "analyze", "正在生成", interval=0.01):
        await asyncio.sleep(0.03)
    assert not [task for task in asyncio.all_tasks() if not task.done() and task is not asyncio.current_task()]
