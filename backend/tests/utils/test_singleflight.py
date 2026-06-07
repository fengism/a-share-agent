import asyncio

import pytest

from app.utils.singleflight import AsyncSingleFlight


@pytest.mark.asyncio
async def test_singleflight_dedupes_concurrent_same_key():
    """AsyncSingleFlight.do deduplicates concurrent calls sharing the same key."""
    singleflight = AsyncSingleFlight[int]()
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return 7

    result_a, result_b = await asyncio.gather(
        singleflight.do("same", loader),
        singleflight.do("same", loader),
    )

    assert (result_a, result_b) == (7, 7)
    assert calls == 1


@pytest.mark.asyncio
async def test_singleflight_does_not_dedupe_different_keys():
    """AsyncSingleFlight.do does not deduplicate concurrent calls with different keys."""
    singleflight = AsyncSingleFlight[str]()
    calls: list[str] = []

    async def load_a():
        calls.append("a")
        await asyncio.sleep(0.01)
        return "a"

    async def load_b():
        calls.append("b")
        await asyncio.sleep(0.01)
        return "b"

    result_a, result_b = await asyncio.gather(
        singleflight.do("a", load_a),
        singleflight.do("b", load_b),
    )

    assert (result_a, result_b) == ("a", "b")
    assert sorted(calls) == ["a", "b"]


@pytest.mark.asyncio
async def test_singleflight_clears_inflight_after_failure():
    """AsyncSingleFlight.do clears inflight state and retries after a loader failure."""
    singleflight = AsyncSingleFlight[str]()
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return "ok"

    with pytest.raises(RuntimeError, match="temporary failure"):
        await singleflight.do("key", loader)

    assert await singleflight.do("key", loader) == "ok"
    assert calls == 2
