import asyncio
import json

import pytest

from app.models.analysis import AnalysisProgress
from app.services.analysis import stream


@pytest.mark.anyio
async def test_create_analysis_event_generator_streams_progress(monkeypatch):
    """create_analysis_event_generator should serialize emitted progress events."""

    async def fake_run_analysis(code: str, progress_callback=None):
        await progress_callback(AnalysisProgress(type="stage_started"))
        await progress_callback(AnalysisProgress(type="complete"))
        return None

    monkeypatch.setattr(stream, "run_analysis", fake_run_analysis)

    generator = await stream.create_analysis_event_generator("600519")
    events = []
    async for item in generator:
        events.append(item)

    assert [event["event"] for event in events] == ["stage_started", "complete"]
    assert json.loads(events[0]["data"])["type"] == "stage_started"


@pytest.mark.anyio
async def test_create_analysis_event_generator_blocks_duplicate_runs(monkeypatch):
    """create_analysis_event_generator should reject a second in-flight run for the same code."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_analysis(code: str, progress_callback=None):
        started.set()
        await release.wait()
        return None

    monkeypatch.setattr(stream, "run_analysis", fake_run_analysis)

    generator = await stream.create_analysis_event_generator("600519")
    await started.wait()

    with pytest.raises(stream.AnalysisAlreadyRunningError):
        await stream.create_analysis_event_generator("600519")

    await generator.aclose()
    release.set()
