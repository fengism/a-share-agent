"""Transient tool failures get a short negative cache; permanent errors do not."""

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo, ToolResultInfo
from app.agentic.tools import cache as cache_module
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.serialization import serialize_error


def _call() -> ToolCallInfo:
    return ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="fake_tool", arguments="{}"),
    )


def _install_tool(monkeypatch, content: str, *, is_error: bool) -> list[ToolCallInfo]:
    calls: list[ToolCallInfo] = []

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        calls.append(call)
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content=content,
            is_error=is_error,
        )

    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=60))
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    return calls


async def test_transient_failure_is_negatively_cached(monkeypatch):
    content = serialize_error("timeout", "upstream slow", retryable=True)
    calls = _install_tool(monkeypatch, content, is_error=True)
    cache = SharedToolCache()

    first, first_shared = await cache.execute_shared(_call())
    second, second_shared = await cache.execute_shared(_call())

    assert first.is_error is True
    assert second.is_error is True
    assert first_shared is False
    assert second_shared is True
    assert len(calls) == 1
    assert second.content == content


async def test_permanent_failure_is_not_negatively_cached(monkeypatch):
    content = serialize_error("invalid_arguments", "bad arguments", retryable=False)
    calls = _install_tool(monkeypatch, content, is_error=True)
    cache = SharedToolCache()

    first, first_shared = await cache.execute_shared(_call())
    second, second_shared = await cache.execute_shared(_call())

    assert first.is_error is True
    assert second.is_error is True
    assert first_shared is False
    assert second_shared is False
    assert len(calls) == 2


async def test_negative_cache_expires(monkeypatch):
    content = serialize_error("upstream_unavailable", "temporary", retryable=True)
    calls = _install_tool(monkeypatch, content, is_error=True)
    monkeypatch.setattr(cache_module, "_NEGATIVE_CACHE_TTL_SECONDS", -1.0)
    cache = SharedToolCache()

    await cache.execute_shared(_call())
    await cache.execute_shared(_call())

    assert len(calls) == 2
