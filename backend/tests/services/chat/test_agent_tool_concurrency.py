import asyncio
import time
from types import SimpleNamespace

import pytest

from app.models.chat import ToolCallFunction, ToolCallInfo, ToolResultInfo
from app.services.chat import agent


def _tool_call(call_id: str) -> ToolCallInfo:
    return ToolCallInfo(
        id=call_id,
        type="function",
        function=ToolCallFunction(name=f"tool_{call_id}", arguments="{}"),
    )


@pytest.mark.asyncio
async def test_execute_tool_calls_ordered_runs_concurrently_and_preserves_order(monkeypatch):
    delays = {"call_1": 0.08, "call_2": 0.01, "call_3": 0.03}
    completed: list[str] = []

    async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
        await asyncio.sleep(delays[call.id])
        completed.append(call.id)
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content=call.id,
            is_error=False,
        )

    monkeypatch.setattr(agent.registry, "execute", fake_execute)
    calls = [_tool_call("call_1"), _tool_call("call_2"), _tool_call("call_3")]

    start = time.perf_counter()
    results = await agent._execute_tool_calls_ordered(calls)
    elapsed = time.perf_counter() - start

    assert elapsed < sum(delays.values())
    assert completed == ["call_2", "call_3", "call_1"]
    assert [result.tool_call_id for result in results] == ["call_1", "call_2", "call_3"]


@pytest.mark.asyncio
async def test_execute_tool_calls_ordered_keeps_error_result_in_place(monkeypatch):
    async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content="failed" if call.id == "call_2" else "ok",
            is_error=call.id == "call_2",
        )

    monkeypatch.setattr(agent.registry, "execute", fake_execute)
    calls = [_tool_call("call_1"), _tool_call("call_2"), _tool_call("call_3")]

    results = await agent._execute_tool_calls_ordered(calls)

    assert [result.tool_call_id for result in results] == ["call_1", "call_2", "call_3"]
    assert [result.is_error for result in results] == [False, True, False]


@pytest.mark.asyncio
async def test_run_chat_agent_generates_final_text_after_max_tool_rounds(monkeypatch):
    calls: list[str] = []

    def fake_create(**kwargs):
        calls.append(kwargs["tool_choice"])
        if kwargs["tool_choice"] == "none":
            return [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="最终结论", tool_calls=None))]
                )
            ]
        return [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=f"call_{len(calls)}",
                                    function=SimpleNamespace(name="dummy_tool", arguments="{}"),
                                )
                            ],
                        )
                    )
                ]
            )
        ]

    async def fake_execute(call: ToolCallInfo) -> ToolResultInfo:
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content="{}",
            is_error=False,
        )

    monkeypatch.setattr(agent.registry, "execute", fake_execute)
    monkeypatch.setattr(agent.registry, "get_tool_definitions", lambda: [])
    monkeypatch.setattr(agent.OpenAI, "chat", SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    deltas = [delta async for delta in agent.run_chat_agent("测试")]

    assert calls == ["required", "auto", "auto", "auto", "auto", "none"]
    assert any(delta.type == "text" and delta.content == "最终结论" for delta in deltas)
    assert deltas[-1].type == "done"
