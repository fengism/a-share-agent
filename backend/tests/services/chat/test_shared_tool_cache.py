"""SharedToolCache 跨子 Agent 去重逻辑测试。"""

import asyncio

from app.models.chat import ToolCallFunction, ToolCallInfo, ToolResultInfo
from app.services.chat.subagents import base


def _make_call(call_id: str, name: str, arguments: str) -> ToolCallInfo:
    return ToolCallInfo(
        id=call_id,
        type="function",
        function=ToolCallFunction(name=name, arguments=arguments),
    )


class TestSharedToolCache:
    async def test_dedup_same_name_args(self, monkeypatch):
        calls: list[str] = []

        async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
            calls.append(call.id)
            return ToolResultInfo(
                tool_call_id=call.id, name=call.function.name, content="data"
            )

        monkeypatch.setattr(base.registry, "execute_tool", fake_execute)
        cache = base.SharedToolCache()

        r1 = await cache.execute(_make_call("a", "get_x", '{"code":"600519"}'))
        r2 = await cache.execute(_make_call("b", "get_x", '{"code":"600519"}'))

        # 底层只执行一次
        assert calls == ["a"]
        # 但每次返回的 tool_call_id 对应各自调用
        assert r1.tool_call_id == "a"
        assert r2.tool_call_id == "b"
        assert r1.content == r2.content == "data"

    async def test_different_args_not_deduped(self, monkeypatch):
        calls: list[str] = []

        async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
            calls.append(call.function.arguments)
            return ToolResultInfo(
                tool_call_id=call.id, name=call.function.name, content="data"
            )

        monkeypatch.setattr(base.registry, "execute_tool", fake_execute)
        cache = base.SharedToolCache()

        await cache.execute(_make_call("a", "get_x", '{"code":"600519"}'))
        await cache.execute(_make_call("b", "get_x", '{"code":"000858"}'))

        assert len(calls) == 2

    async def test_concurrent_calls_execute_once(self, monkeypatch):
        calls: list[str] = []

        async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
            calls.append(call.id)
            await asyncio.sleep(0.01)  # 模拟 I/O，制造并发窗口
            return ToolResultInfo(
                tool_call_id=call.id, name=call.function.name, content="data"
            )

        monkeypatch.setattr(base.registry, "execute_tool", fake_execute)
        cache = base.SharedToolCache()

        results = await asyncio.gather(
            cache.execute(_make_call("a", "get_x", "{}")),
            cache.execute(_make_call("b", "get_x", "{}")),
            cache.execute(_make_call("c", "get_x", "{}")),
        )

        # 并发的相同调用只触发一次底层执行
        assert len(calls) == 1
        assert {r.tool_call_id for r in results} == {"a", "b", "c"}

    async def test_failure_not_cached(self, monkeypatch):
        attempts: list[str] = []

        async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
            attempts.append(call.id)
            raise RuntimeError("boom")

        monkeypatch.setattr(base.registry, "execute_tool", fake_execute)
        cache = base.SharedToolCache()

        for cid in ("a", "b"):
            try:
                await cache.execute(_make_call(cid, "get_x", "{}"))
            except RuntimeError:
                pass

        # 失败不缓存，第二次重新尝试
        assert attempts == ["a", "b"]
