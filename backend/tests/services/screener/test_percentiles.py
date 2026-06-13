import asyncio

import pytest

from app.services.screener import percentiles


@pytest.mark.asyncio
async def testcompute_percentiles_dedupes_and_preserves_input_order(monkeypatch):
    """compute_percentiles deduplicates codes and preserves the input order in results."""
    calls: list[str] = []

    async def fake_compute(code: str, indicator: str, period: str):
        calls.append(code)
        return {"600519": 10.0, "000858": 20.0}[code]

    monkeypatch.setattr(percentiles, "compute_percentile", fake_compute)
    percentiles._percentile_inflight.clear()

    result = await percentiles.compute_percentiles(
        ["600519", "000858", "600519"],
        "市盈率(TTM)",
        "近三年",
    )

    assert result == [
        {"code": "600519", "percentile": 10.0},
        {"code": "000858", "percentile": 20.0},
        {"code": "600519", "percentile": 10.0},
    ]
    assert calls == ["600519", "000858"]


@pytest.mark.asyncio
async def testcompute_percentiles_limits_concurrency(monkeypatch):
    """compute_percentiles caps the number of concurrent per-code computations."""
    running = 0
    max_running = 0
    lock = asyncio.Lock()

    async def fake_compute(code: str, indicator: str, period: str):
        nonlocal running, max_running
        async with lock:
            running += 1
            max_running = max(max_running, running)
        await asyncio.sleep(0.01)
        async with lock:
            running -= 1
        return 1.0

    monkeypatch.setattr(percentiles, "compute_percentile", fake_compute)
    percentiles._percentile_inflight.clear()

    await percentiles.compute_percentiles([f"6005{i:02d}" for i in range(10)])

    assert max_running <= percentiles._PERCENTILE_CONCURRENCY


@pytest.mark.asyncio
async def testcompute_percentiles_dedupes_inflight_across_requests(monkeypatch):
    """compute_percentiles deduplicates inflight computations across concurrent requests."""
    calls = 0

    async def fake_compute(code: str, indicator: str, period: str):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return 33.3

    monkeypatch.setattr(percentiles, "compute_percentile", fake_compute)
    percentiles._percentile_inflight.clear()

    result_a, result_b = await asyncio.gather(
        percentiles.compute_percentiles(["600519"]),
        percentiles.compute_percentiles(["600519"]),
    )

    assert result_a == [{"code": "600519", "percentile": 33.3}]
    assert result_b == [{"code": "600519", "percentile": 33.3}]
    assert calls == 1


@pytest.mark.asyncio
async def testcompute_percentiles_handles_per_code_errors(monkeypatch):
    """compute_percentiles captures per-code errors and returns None for failed entries."""
    async def fake_compute(code: str, indicator: str, period: str):
        if code == "600519":
            raise RuntimeError("provider failed")
        return 20.0

    monkeypatch.setattr(percentiles, "compute_percentile", fake_compute)
    percentiles._percentile_inflight.clear()

    result = await percentiles.compute_percentiles(["600519", "000858"])

    assert result == [
        {"code": "600519", "percentile": None},
        {"code": "000858", "percentile": 20.0},
    ]
