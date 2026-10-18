"""Shared cache keys must stay scoped and reusable by the executor."""

import asyncio
import json
from types import SimpleNamespace

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo, ToolResultInfo
from app.agentic.tools.cache import SharedToolCache, _SharedToolCacheEntry
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.serialization import tool_call_cache_key, tool_call_cache_key_from_arguments


def _call() -> ToolCallInfo:
    return ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="fake_tool", arguments='{"code":"600519"}'),
    )


def test_user_scoped_key_partitions_by_user(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(scope="user"))
    cache = SharedToolCache()

    first = cache.cache_key_for(_call(), SimpleNamespace(user_id=1))
    second = cache.cache_key_for(_call(), SimpleNamespace(user_id=2))

    assert first != second
    assert ":user:1:" in first
    assert ":user:2:" in second


def test_public_scope_key_has_no_user_partition(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(scope="public"))
    cache = SharedToolCache()

    key = cache.cache_key_for(_call(), SimpleNamespace(user_id=1))

    assert ":user:" not in key


async def test_get_cached_result_accepts_precomputed_key(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy())
    cache = SharedToolCache()
    call = _call()
    future: asyncio.Future[ToolResultInfo] = asyncio.get_running_loop().create_future()
    future.set_result(ToolResultInfo(
        tool_call_id=call.id,
        name=call.function.name,
        content='{"ok":true,"data":{"code":"600519"}}',
    ))
    cache._cache["precomputed"] = _SharedToolCacheEntry(future=future)

    def fail(*args, **kwargs):
        raise AssertionError("cache key should not be recomputed")

    monkeypatch.setattr(cache, "_cache_key", fail)

    result = cache.get_cached_result(call, cache_key="precomputed")

    assert result is not None
    assert result.tool_call_id == call.id


def test_cache_key_from_arguments_matches_string_key():
    call = _call()

    from_arguments = tool_call_cache_key_from_arguments(
        call.function.name,
        json.loads(call.function.arguments),
    )

    assert from_arguments == tool_call_cache_key(call)


def test_cache_key_for_arguments_respects_user_scope(monkeypatch):
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(scope="user"))
    cache = SharedToolCache()

    key = cache.cache_key_for_arguments(
        "fake_tool",
        {"code": "600519"},
        SimpleNamespace(user_id=1),
    )

    assert ":user:1:" in key


async def test_execute_shared_forwards_prepared_arguments(monkeypatch):
    recorded: dict = {}

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        recorded["arguments"] = arguments
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content='{"ok":true,"data":{}}',
        )

    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    cache = SharedToolCache()

    await cache.execute_shared(_call(), arguments={"code": "600519"})

    assert recorded["arguments"] == {"code": "600519"}
