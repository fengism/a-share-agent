"""协议不变量：assistant.tool_calls 与 role=tool 必须严格配对。

配错一次，请求就是 400；而配对逻辑散落在「批内去重回填、预算拒绝、上下文耗尽、
缓存重放、轮次耗尽」五条路径上，任何一条漏写一个 tool 消息都会静默生效直到线上。
每条发出的请求都整体校验一遍。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import AgentExecutor
from app.agentic.catalog import registry
from app.agentic.protocol import ToolResultInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.contracts import ToolPolicy
from app.configuration import get_settings

_TOOL = "pairing_tool"
_DEFINITION = {
    "type": "function",
    "function": {
        "name": _TOOL,
        "description": "d",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}
OK = ('{"ok":true,"data":{"v":1}}', False)
FAIL = ('{"ok":false,"error":{"code":"timeout","message":"x"}}', True)


def _assert_paired(messages: list[dict[str, Any]], where: str) -> None:
    pending: list[str] = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if role == "assistant":
            assert not pending, f"{where}: assistant@{index} 前有未回复的 tool_call {pending}"
            pending = [call["id"] for call in (message.get("tool_calls") or [])]
        elif role == "tool":
            tool_call_id = message.get("tool_call_id")
            assert tool_call_id in pending, (
                f"{where}: tool@{index} 的 tool_call_id={tool_call_id!r} 不在待回复 {pending}"
            )
            pending.remove(tool_call_id)
            assert message.get("content"), f"{where}: tool@{index} 内容为空"
        elif role == "user":
            assert not pending, f"{where}: user@{index} 前有未回复的 tool_call {pending}"
    assert not pending, f"{where}: 结尾仍有未回复的 tool_call {pending}"


class _Completions:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def __call__(self, client, **kwargs):
        self.requests.append(kwargs)
        if self._responses:
            return self._responses.pop(0)
        return _final()


def _final() -> dict:
    return {"choices": [{"message": {"content": "结论", "tool_calls": []}, "finish_reason": "stop"}]}


def _calls(items: list[tuple[str, str, str]]) -> dict:
    return {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [
                    {"id": i, "type": "function", "function": {"name": n, "arguments": a}}
                    for i, n, a in items
                ],
            },
            "finish_reason": "tool_calls",
        }],
    }


def _ids(*names: str) -> dict:
    return _calls([(name, _TOOL, "{}") for name in names])


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[dict],
    results: list[tuple[str, bool]],
    **settings,
) -> _Completions:
    completions = _Completions(responses)
    executed: list[str] = []

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        executed.append(call.id)
        content, is_error = results[min(len(executed) - 1, len(results) - 1)]
        return ToolResultInfo(
            tool_call_id=call.id, name=call.function.name, content=content, is_error=is_error,
        )

    # 必须用 monkeypatch：直接给全局 registry 赋值会污染后续测试（这里踩过）。
    monkeypatch.setattr(registry, "get_tool_definitions_for", lambda names: [_DEFINITION])
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    import app.agentic.agents.executor as executor_module

    monkeypatch.setattr(executor_module, "create_chat_completion", completions)
    await AgentExecutor().run(
        AgentProfile(
            name="pairing-agent",
            display_name="配对",
            description="d",
            system_prompt="s",
            tool_names=(_TOOL,),
            max_rounds=4,
        ),
        "问题",
        None,
        object(),
        "m",
        execution_context=AgentExecutionContext(
            settings=get_settings().model_copy(update=settings)
        ),
        require_tool_first_round=True,
    )

    assert completions.requests, "至少要发出一次请求"
    for index, request in enumerate(completions.requests):
        _assert_paired(request["messages"], f"req{index}")
    return completions


@pytest.mark.asyncio
async def test_two_sequential_tool_rounds(monkeypatch):
    await _run(
        monkeypatch, [_ids("a1"), _ids("a2")], [OK])


@pytest.mark.asyncio
async def test_same_id_repeated_in_one_batch(monkeypatch):
    await _run(
        monkeypatch,[_calls([("d1", _TOOL, "{}"), ("d1", _TOOL, "{}")])], [OK])


@pytest.mark.asyncio
async def test_distinct_ids_with_identical_arguments_are_deduplicated(monkeypatch):
    """真实去重场景：cache_key 相同但 id 不同，回填必须为每个 id 都给出 tool 消息。"""
    completions = await _run(
        monkeypatch, [_calls([("x1", _TOOL, "{}"), ("x2", _TOOL, "{}")])], [OK]
    )
    tool_messages = [m for m in completions.requests[-1]["messages"] if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["x1", "x2"]


@pytest.mark.asyncio
async def test_budget_rejection_still_answers_every_call(monkeypatch):
    await _run(
        monkeypatch, [_ids("b1", "b2", "b3")], [OK], chat_max_tool_calls=1)


@pytest.mark.asyncio
async def test_context_exhaustion_still_answers_every_call(monkeypatch):
    await _run(
        monkeypatch,
        [_ids("e1"), _ids("e2", "e3")],
        [('{"ok":true,"data":{"text":"%s"}}' % ("数" * 9_000), False)],
        chat_max_tool_context_characters=4_096,
    )


@pytest.mark.asyncio
async def test_tool_failure_then_success(monkeypatch):
    await _run(
        monkeypatch, [_ids("g1"), _ids("g2")], [FAIL, OK])


@pytest.mark.asyncio
async def test_round_limit_reached_mid_tool_round(monkeypatch):
    await _run(
        monkeypatch, [_ids("h1"), _ids("h2"), _ids("h3"), _ids("h4")], [OK])
