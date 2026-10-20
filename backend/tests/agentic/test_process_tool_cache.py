"""Process-wide tool result cache: only public, slow-changing results may be shared.

``SharedToolCache`` is per-request, so `ToolPolicy.cache_ttl_seconds` used to be
honoured only inside one agent run. These tests pin the cross-request behaviour
and, more importantly, the boundaries: user-scoped and realtime results must
never leak between requests.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.process_cache import ProcessToolCache, process_tool_cache
from app.configuration import get_settings

_DAILY_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=900, freshness="daily")
_STATIC_POLICY = ToolPolicy(cache_ttl_seconds=3600, freshness="static")


def _call(call_id: str = "call_1", name: str = "fake_daily") -> ToolCallInfo:
    return ToolCallInfo(
        id=call_id,
        type="function",
        function={"name": name, "arguments": "{}"},
    )


def _context(**updates) -> AgentExecutionContext:
    return AgentExecutionContext(settings=get_settings().model_copy(update=updates))


@pytest.fixture(autouse=True)
def _clean_process_cache():
    process_tool_cache.clear()
    yield
    process_tool_cache.clear()


def test_eligibility_is_narrow():
    cache = ProcessToolCache()
    assert cache.eligible(_DAILY_POLICY) is True
    assert cache.eligible(_STATIC_POLICY) is True
    # Realtime data changes between requests.
    assert cache.eligible(ToolPolicy(cache_ttl_seconds=30, freshness="realtime")) is False
    # Never reuse a ttl=0 tool.
    assert cache.eligible(ToolPolicy(cache_ttl_seconds=0, freshness="daily")) is False
    # Per-user results depend on private configuration.
    assert cache.eligible(ToolPolicy(cache_ttl_seconds=900, freshness="daily", scope="user")) is False
    # Side-effecting calls (not even deduplicable inside one batch) must never
    # be answered from a previous request, even if a TTL were configured.
    assert cache.eligible(
        ToolPolicy(cache_ttl_seconds=900, freshness="daily", deduplicate_in_batch=False)
    ) is False


def test_entries_expire_and_are_bounded():
    cache = ProcessToolCache(max_entries=2)
    cache.put("a", ToolResultInfo(tool_call_id="1", name="t", content="A"), ttl_seconds=100)
    cache.put("b", ToolResultInfo(tool_call_id="1", name="t", content="B"), ttl_seconds=100)
    cache.put("c", ToolResultInfo(tool_call_id="1", name="t", content="C"), ttl_seconds=100)

    assert len(cache) == 2
    assert cache.get("a", "call") is None  # oldest evicted
    assert cache.get("c", "call").content == "C"

    cache.put("d", ToolResultInfo(tool_call_id="1", name="t", content="D"), ttl_seconds=0.0)
    assert cache.get("d", "call") is None


def test_expired_entry_is_dropped():
    cache = ProcessToolCache()
    cache.put("x", ToolResultInfo(tool_call_id="1", name="t", content="X"), ttl_seconds=-1.0)
    assert cache.get("x", "call") is None


def test_errors_and_oversized_payloads_are_not_stored():
    cache = ProcessToolCache()
    cache.put("e", ToolResultInfo(tool_call_id="1", name="t", content="{}", is_error=True), 100)
    cache.put("big", ToolResultInfo(tool_call_id="1", name="t", content="x" * 24_001), 100)

    assert len(cache) == 0


def test_get_returns_a_per_call_copy():
    cache = ProcessToolCache()
    cache.put("k", ToolResultInfo(tool_call_id="original", name="t", content="V"), 100)

    first = cache.get("k", "call_a")
    second = cache.get("k", "call_b")

    assert first.tool_call_id == "call_a"
    assert second.tool_call_id == "call_b"
    assert first.name == "t" and first.content == "V"


async def _run_once(cache: SharedToolCache, context: AgentExecutionContext, executed: list) -> tuple:
    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        executed.append(call.id)
        return ToolResultInfo(
            tool_call_id=call.id, name=call.function.name, content='{"ok":true,"data":{"v":1}}'
        )

    original = registry.execute_tool
    registry.execute_tool = fake_execute
    try:
        return await cache.execute_shared(_call(), allowed_names=None, execution_context=context)
    finally:
        registry.execute_tool = original


async def test_daily_result_is_reused_across_requests(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: _DAILY_POLICY)
    executed: list[str] = []

    first, first_shared = await _run_once(SharedToolCache(), _context(), executed)
    second, second_shared = await _run_once(SharedToolCache(), _context(), executed)

    assert first_shared is False
    assert second_shared is True
    assert executed == ["call_1"]  # upstream hit exactly once
    assert second.content == first.content


async def test_user_scoped_result_is_not_shared_across_requests(monkeypatch):
    monkeypatch.setattr(
        registry,
        "get_tool_policy",
        lambda name: ToolPolicy(cache_ttl_seconds=900, freshness="daily", scope="user"),
    )
    executed: list[str] = []

    await _run_once(SharedToolCache(), _context(user_id=1), executed)
    _, second_shared = await _run_once(SharedToolCache(), _context(user_id=2), executed)

    assert second_shared is False
    assert executed == ["call_1", "call_1"]


async def test_realtime_result_is_not_shared_across_requests(monkeypatch):
    monkeypatch.setattr(
        registry,
        "get_tool_policy",
        lambda name: ToolPolicy(cache_ttl_seconds=30, freshness="realtime"),
    )
    executed: list[str] = []

    await _run_once(SharedToolCache(), _context(), executed)
    _, second_shared = await _run_once(SharedToolCache(), _context(), executed)

    assert second_shared is False
    assert executed == ["call_1", "call_1"]


async def test_process_cache_toggle_disables_reuse(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: _DAILY_POLICY)
    executed: list[str] = []

    await _run_once(SharedToolCache(), _context(chat_tool_process_cache_enabled=False), executed)
    _, second_shared = await _run_once(
        SharedToolCache(), _context(chat_tool_process_cache_enabled=False), executed
    )

    assert second_shared is False
    assert executed == ["call_1", "call_1"]


async def test_standalone_run_without_execution_context_is_isolated(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: _DAILY_POLICY)
    executed: list[str] = []

    await _run_once(SharedToolCache(), None, executed)
    _, second_shared = await _run_once(SharedToolCache(), None, executed)

    assert second_shared is False
    assert executed == ["call_1", "call_1"]


async def test_get_cached_result_consults_the_process_cache(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: _DAILY_POLICY)
    executed: list[str] = []
    context = _context()

    await _run_once(SharedToolCache(), context, executed)
    replay = SharedToolCache().get_cached_result(
        _call(call_id="call_2"), allowed_names=None, execution_context=context
    )

    assert replay is not None
    assert replay.tool_call_id == "call_2"
    assert executed == ["call_1"]


async def test_concurrent_requests_each_execute_but_the_next_one_reuses(monkeypatch):
    """Cross-request coalescing is not attempted; only completed results are reused."""
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: _DAILY_POLICY)
    executed: list[str] = []
    release = asyncio.Event()

    async def slow_execute(call, allowed_names=None, execution_context=None, arguments=None):
        executed.append(call.id)
        await release.wait()
        return ToolResultInfo(tool_call_id=call.id, name=call.function.name, content='{"ok":true}')

    original = registry.execute_tool
    registry.execute_tool = slow_execute
    try:
        first = asyncio.create_task(
            SharedToolCache().execute_shared(_call(), execution_context=_context())
        )
        await asyncio.sleep(0)
        second = asyncio.create_task(
            SharedToolCache().execute_shared(_call(), execution_context=_context())
        )
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
        third, third_shared = await SharedToolCache().execute_shared(
            _call(), execution_context=_context()
        )
    finally:
        registry.execute_tool = original

    # Both in-flight requests ran; the completed result is then reused.
    assert executed == ["call_1", "call_1"]
    assert [shared for _, shared in results] == [False, False]
    assert third_shared is True
    assert third.content == '{"ok":true}'


def test_cross_request_ttl_is_capped_regardless_of_the_policy():
    """`freshness="static"` 的 ttl 可能是 3600s；错声明不能变成一小时全局陈旧值。"""
    from app.agentic.tools.process_cache import _MAX_CROSS_REQUEST_TTL_SECONDS

    cache = ProcessToolCache()
    cache.put("k", ToolResultInfo(tool_call_id="1", name="t", content="V"), ttl_seconds=3600)

    entry = cache._entries["k"]
    assert entry.expires_at <= time.monotonic() + _MAX_CROSS_REQUEST_TTL_SECONDS + 1
