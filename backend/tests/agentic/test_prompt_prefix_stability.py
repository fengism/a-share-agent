"""Prompt-prefix stability: static content first, volatile content last, append-only rounds.

Providers cache the longest common prefix of a prompt. Two invariants keep that
cache useful for the multi-round agent loop:

1. Within one system prompt the per-second runtime clock must be the trailing
   section, so the static Skill/tool rules stay cacheable.
2. Across the rounds of one run the message list must only grow at the tail.
   Rewriting an early message invalidates every token after it.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import AgentExecutor
from app.agentic.catalog import registry
from app.agentic.messages import _RUNTIME_DATE_SECTION, _runtime_date_context, build_messages
from app.agentic.protocol import ToolResultInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.runtime.research_policy import ResearchSearchPolicy
from app.agentic.runtime.timezones import SHANGHAI_TIMEZONE
from app.agentic.tools.contracts import ToolPolicy
from app.configuration import get_settings

_SEARCH_TOOL = "fake_search"
_READ_TOOL = "fake_read"
_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": "test tool",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    }
    for name in (_SEARCH_TOOL, _READ_TOOL)
]


class _FakeClient:
    def __init__(self) -> None:
        self.capabilities: Any = None


class _SnapshottingCompletions:
    """Records a deep copy of every request, since the executor reuses one list."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def __call__(self, client, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        if not self._responses:
            raise AssertionError("unexpected completion request")
        return self._responses.pop(0)


def _search_response(call_id: str, query: str) -> dict:
    return {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {"name": _SEARCH_TOOL, "arguments": f'{{"query":"{query}"}}'},
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


def _final_response(content: str = "最终结论") -> dict:
    return {
        "choices": [{
            "message": {"content": content, "tool_calls": []},
            "finish_reason": "stop",
        }],
    }


def _profile() -> AgentProfile:
    return AgentProfile(
        name="prefix-agent",
        display_name="前缀测试 Agent",
        description="prompt prefix test",
        system_prompt="system",
        tool_names=(_SEARCH_TOOL, _READ_TOOL),
        max_rounds=3,
    )


def _search_policy() -> ResearchSearchPolicy:
    return ResearchSearchPolicy(
        tool_names=(_SEARCH_TOOL,),
        total_limit=5,
        burst_limit=2,
        read_tool_names=(_READ_TOOL,),
    )


def _install_registry(monkeypatch) -> None:
    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        # A search hit with a real URL changes the pacing guidance for the next round.
        content = '{"ok":true,"data":{"results":[{"url":"https://example.com/a","title":"A"}]}}'
        policy = execution_context.search_policy if execution_context is not None else None
        if policy is not None:
            policy.observe(call.function.name, call.function.arguments, content, is_error=False)
            policy.finish_batch()
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content=content,
            is_error=False,
        )

    monkeypatch.setattr(
        registry,
        "get_tool_definitions_for",
        lambda names: [item for item in _TOOL_DEFINITIONS if item["function"]["name"] in names],
    )
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)


def test_runtime_clock_is_the_trailing_system_section():
    frozen_now = datetime(2026, 2, 3, 9, 30, 0, tzinfo=SHANGHAI_TIMEZONE)
    messages = build_messages(
        "问题",
        None,
        max_history_messages=5,
        system_prompt="STATIC-SYSTEM",
        tool_selection_prompt="STATIC-SKILL-RULES",
        current_time=frozen_now,
    )

    content = messages[0]["content"]
    assert content.index("STATIC-SYSTEM") < content.index("STATIC-SKILL-RULES")
    assert content.index("STATIC-SKILL-RULES") < content.index(_RUNTIME_DATE_SECTION)
    # Nothing static or volatile may follow the clock section.
    assert "STATIC" not in content[content.index(_RUNTIME_DATE_SECTION):]
    assert _runtime_date_context(frozen_now) in content


def test_history_stays_between_system_prompt_and_current_message():
    from app.agentic.protocol import AgentMessage

    messages = build_messages(
        "现在的问题",
        [AgentMessage(role="user", content="旧问题"), AgentMessage(role="assistant", content="旧回答")],
        max_history_messages=5,
        system_prompt="system",
        tool_selection_prompt="rules",
    )

    assert [item["role"] for item in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "现在的问题"


async def test_agent_rounds_only_append_to_the_message_tail(monkeypatch):
    completions = _SnapshottingCompletions([
        _search_response("call_1", "第一个查询"),
        _search_response("call_2", "第二个查询"),
        _final_response(),
    ])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch)

    context = AgentExecutionContext(
        settings=get_settings(),
        search_policy=_search_policy(),
    )
    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=context,
        require_tool_first_round=True,
    )

    assert result.status == "completed"
    assert len(completions.requests) == 3
    rounds = [request["messages"] for request in completions.requests]
    for previous, current in zip(rounds, rounds[1:]):
        # Same prefix, tail extended: this is what a provider prefix cache needs.
        assert current[: len(previous)] == previous
        assert len(current) > len(previous)
    # The changing pacing guidance must have been appended, never rewritten.
    assert sum(
        1 for message in rounds[-1] if message["role"] == "user" and "搜索组已执行" in message["content"]
    ) == 3


async def test_repeated_guidance_is_not_reappended(monkeypatch):
    completions = _SnapshottingCompletions([
        _search_response("call_1", "查询"),
        _final_response(),
    ])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch)

    policy = _search_policy()
    monkeypatch.setattr(policy, "instruction", lambda: "固定节奏提示", raising=False)
    context = AgentExecutionContext(settings=get_settings(), search_policy=policy)
    await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=context,
        require_tool_first_round=True,
    )

    messages = completions.requests[-1]["messages"]
    assert sum(
        1 for message in messages if message["role"] == "user" and "固定节奏提示" in message["content"]
    ) == 1
