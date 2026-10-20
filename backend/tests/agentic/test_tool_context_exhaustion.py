"""工具上下文预算耗尽后不该继续花钱执行工具。

判据从「`>= 上限`」放宽为「剩余额度连每条一个合法占位都放不下」：只剩个位数字符时
照样一条有效内容都送不出去，但工具配额、上游调用和 LLM 往返会全部照常消耗。
"""

from __future__ import annotations

import json

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import AgentExecutor
from app.agentic.catalog import registry
from app.agentic.protocol import ToolResultInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.contracts import ToolPolicy
from app.configuration import get_settings

_TOOL = "big_tool"
_DEFINITION = {
    "type": "function",
    "function": {
        "name": _TOOL,
        "description": "test tool",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}
_BUDGET = 4_096  # chat_max_tool_context_characters 的下限


class _Client:
    pass


class _Completions:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def __call__(self, client, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


def _calls(count: int, round_index: int) -> dict:
    return {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "id": f"c{round_index}_{index}",
                        "type": "function",
                        "function": {"name": _TOOL, "arguments": json.dumps({"i": index})},
                    }
                    for index in range(count)
                ],
            },
            "finish_reason": "tool_calls",
        }],
    }


def _final() -> dict:
    return {"choices": [{"message": {"content": "结论", "tool_calls": []}, "finish_reason": "stop"}]}


def _profile() -> AgentProfile:
    return AgentProfile(
        name="budget-agent",
        display_name="预算",
        description="budget test",
        system_prompt="system",
        tool_names=(_TOOL,),
        max_rounds=3,
    )


def _install(monkeypatch, size: int) -> list:
    executed: list = []
    payload = json.dumps({"ok": True, "data": {"text": "数" * size}}, ensure_ascii=False)

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        executed.append(call)
        return ToolResultInfo(
            tool_call_id=call.id, name=call.function.name, content=payload, is_error=False,
        )

    monkeypatch.setattr(registry, "get_tool_definitions_for", lambda names: [_DEFINITION])
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    return executed


async def test_nearly_exhausted_budget_skips_execution_entirely(monkeypatch):
    # 第一轮用一条巨大结果把预算吃光，第二轮再发 8 个调用。
    completions = _Completions([_calls(1, 1), _calls(8, 2), _final()])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    executed = _install(monkeypatch, size=_BUDGET * 2)

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _Client(),
        "fake-model",
        execution_context=AgentExecutionContext(
            settings=get_settings().model_copy(
                update={"chat_max_tool_context_characters": _BUDGET}
            )
        ),
        require_tool_first_round=True,
    )

    assert len(executed) == 1, "预算耗尽后的第二批调用不该真的执行"
    assert any("工具上下文预算不足" in warning for warning in result.warnings)
    # 被拒的调用仍然要告诉模型「别再调了」，且内容必须是合法 JSON。
    tool_messages = [
        message
        for message in completions.requests[-1]["messages"]
        if message.get("role") == "tool"
    ]
    assert tool_messages
    for message in tool_messages:
        assert json.loads(message["content"]) is not None or message["content"] == "null"


def test_exhaustion_rule_has_an_explicit_boundary():
    from app.agentic.agents.executor import _tool_context_exhausted
    from app.agentic.tools.serialization import EMPTY_TOOL_RESULT

    placeholder = len(EMPTY_TOOL_RESULT)
    # 每个待执行调用至少要能拿到一个合法占位，否则执行了也送不出去。
    assert _tool_context_exhausted(placeholder * 8 - 1, 8) is True
    assert _tool_context_exhausted(placeholder * 8, 8) is False
    assert _tool_context_exhausted(0, 8) is True
    assert _tool_context_exhausted(-100, 3) is True
    # 单个调用只需一个占位即可；没有待执行调用时不该报耗尽。
    assert _tool_context_exhausted(placeholder, 1) is False
    assert _tool_context_exhausted(0, 0) is False
