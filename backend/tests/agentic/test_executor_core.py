"""Core AgentExecutor loop: tool round, dedupe, reasoning budget, failure labels."""

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import _MAX_REPLAY_REASONING_CHARACTERS, AgentExecutor
from app.agentic.catalog import registry
from app.agentic.protocol import ToolResultInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.contracts import ToolPolicy
from app.agentic.tools.serialization import serialize_error
from app.configuration import get_settings
from app.infrastructure.llm.capabilities import DEFAULT_LLM_CAPABILITIES

_FAKE_TOOL = "fake_tool"
_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": _FAKE_TOOL,
        "description": "test tool",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


class _FakeClient:
    def __init__(self, capabilities: Any = None) -> None:
        if capabilities is not None:
            self.capabilities = capabilities


class _FakeCompletions:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def __call__(self, client, **kwargs):
        self.requests.append(kwargs)
        if not self._responses:
            raise AssertionError("unexpected completion request")
        return self._responses.pop(0)


def _tool_call_response(
    *,
    call_id: str = "call_1",
    reasoning_content: str = "",
) -> dict:
    return {
        "choices": [{
            "message": {
                "content": "",
                "reasoning_content": reasoning_content,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {"name": _FAKE_TOOL, "arguments": "{}"},
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


def _two_tool_call_response() -> dict:
    response = _tool_call_response(call_id="call_1")
    second = _tool_call_response(call_id="call_2")["choices"][0]["message"]["tool_calls"][0]
    response["choices"][0]["message"]["tool_calls"].append(second)
    return response


def _final_response(content: str = "最终结论") -> dict:
    return {
        "choices": [{
            "message": {"content": content, "tool_calls": []},
            "finish_reason": "stop",
        }],
    }


def _profile() -> AgentProfile:
    return AgentProfile(
        name="test-agent",
        display_name="测试 Agent",
        description="executor test",
        system_prompt="system",
        tool_names=(_FAKE_TOOL,),
        max_rounds=2,
    )


def _context(**updates) -> AgentExecutionContext:
    settings = get_settings().model_copy(update=updates)
    return AgentExecutionContext(settings=settings)


def _install_registry(
    monkeypatch,
    results: list[tuple[str, bool]],
) -> list:
    executed: list = []

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        executed.append(call)
        content, is_error = results[min(len(executed) - 1, len(results) - 1)]
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content=content,
            is_error=is_error,
        )

    monkeypatch.setattr(
        registry,
        "get_tool_definitions_for",
        lambda names: [_TOOL_DEFINITION] if _FAKE_TOOL in names else [],
    )
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    return executed


async def test_executor_runs_tool_then_final_answer(monkeypatch):
    completions = _FakeCompletions([_tool_call_response(), _final_response("最终结论")])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    executed = _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    assert result.status == "completed"
    assert result.analysis == "最终结论"
    assert result.tools_called == [_FAKE_TOOL]
    assert len(executed) == 1
    assert result.tool_results[0].has_evidence is True
    assert len(completions.requests) == 2


async def test_executor_deduplicates_identical_tool_calls(monkeypatch):
    completions = _FakeCompletions([_two_tool_call_response(), _final_response()])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    executed = _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    assert len(executed) == 1
    assert [item.skipped for item in result.tool_results] == [False, True]


async def test_executor_counts_only_really_used_tools(monkeypatch):
    """``tool_called:<name>`` must not inflate on deduplicated duplicates."""
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    completions = _FakeCompletions([_two_tool_call_response(), _final_response()])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

    await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    events = fresh.snapshot()["agentic"]["events"]
    assert events[f"tool_called:{_FAKE_TOOL}"] == 1


async def test_executor_bounds_replayed_reasoning(monkeypatch):
    capabilities = replace(DEFAULT_LLM_CAPABILITIES, replay_tool_reasoning=True)
    completions = _FakeCompletions([
        _tool_call_response(reasoning_content="R" * 10_000),
        _final_response(),
    ])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(capabilities),
        "fake-model",
        execution_context=_context(chat_max_tool_context_characters=60_000),
        require_tool_first_round=True,
    )

    assistant_messages = [
        message
        for message in completions.requests[1]["messages"]
        if message.get("role") == "assistant" and message.get("tool_calls")
    ]
    assert len(assistant_messages) == 1
    assert len(assistant_messages[0]["reasoning_content"]) == _MAX_REPLAY_REASONING_CHARACTERS
    assert any("推理内容已按上下文预算截断" in warning for warning in result.warnings)


async def test_executor_does_not_store_raw_tool_error_in_errors(monkeypatch):
    completions = _FakeCompletions([_tool_call_response(), _final_response()])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch, [(
        serialize_error("upstream_unavailable", "secret provider detail", retryable=True),
        True,
    )])

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    assert result.status == "partial"
    assert any("fake_tool: 数据源暂不可用" in error for error in result.errors)
    assert all("secret" not in error for error in result.errors)


async def test_executor_skips_tools_when_budget_exhausted(monkeypatch):
    completions = _FakeCompletions([_final_response("预算不足下的结论")])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    executed = _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(chat_max_tool_calls_total=0),
        require_tool_first_round=True,
    )

    assert executed == []
    assert result.status == "partial"
    assert any("额度" in warning for warning in result.warnings)
    assert "tools" not in completions.requests[0]


async def test_executor_load_skill_is_not_data_evidence(monkeypatch):
    definition = {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "load a skill",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    }
    tool_call = {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "load_skill", "arguments": '{"name":"skill_a"}'},
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }
    completions = _FakeCompletions([tool_call, _final_response("最终结论")])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content='{"ok":true,"data":{"kind":"skill_instructions","instructions":"rule-a"}}',
        )

    monkeypatch.setattr(
        registry,
        "get_tool_definitions_for",
        lambda names: [definition] if "load_skill" in names else [],
    )
    monkeypatch.setattr(
        registry,
        "get_tool_policy",
        lambda name: ToolPolicy(cache_ttl_seconds=0, evidence=False),
    )
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    profile = AgentProfile(
        name="test-agent",
        display_name="测试 Agent",
        description="executor test",
        system_prompt="system",
        tool_names=("load_skill",),
        max_rounds=2,
    )

    result = await AgentExecutor().run(
        profile,
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    assert result.status == "completed"
    assert result.tool_results[0].instruction is True
    assert result.tool_results[0].has_evidence is False
    assert result.has_context_evidence is False


async def test_executor_expands_tools_after_load_skill(monkeypatch):
    load_definition = {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "load a skill",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    }
    data_definition = {
        "type": "function",
        "function": {
            "name": "new_tool",
            "description": "new data tool",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
    definitions = {
        "load_skill": load_definition,
        "new_tool": data_definition,
    }
    parameters = {
        "load_skill": load_definition["function"]["parameters"],
        "new_tool": data_definition["function"]["parameters"],
    }
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "load_skill", "arguments": '{"name":"skill_a"}'},
        }]}, "finish_reason": "tool_calls"}]},
        {"choices": [{"message": {"content": "", "tool_calls": [{
            "id": "call_2", "type": "function",
            "function": {"name": "new_tool", "arguments": "{}"},
        }]}, "finish_reason": "tool_calls"}]},
        _final_response("最终结论"),
    ]
    completions = _FakeCompletions(responses)
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        if call.function.name == "load_skill":
            content = '{"ok":true,"data":{"kind":"skill_instructions","tools":["new_tool"]}}'
        else:
            content = '{"ok":true,"data":{"value":1}}'
        return ToolResultInfo(tool_call_id=call.id, name=call.function.name, content=content)

    monkeypatch.setattr(
        registry,
        "get_tool_definitions_for",
        lambda names: [definitions[name] for name in names if name in definitions],
    )
    monkeypatch.setattr(
        registry,
        "get_tool_policy",
        lambda name: ToolPolicy(cache_ttl_seconds=0, evidence=name != "load_skill"),
    )
    monkeypatch.setattr(
        registry,
        "get_tool",
        lambda name: SimpleNamespace(parameters=parameters[name]) if name in parameters else None,
    )
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    profile = AgentProfile(
        name="test-agent",
        display_name="测试 Agent",
        description="executor test",
        system_prompt="system",
        tool_names=("load_skill",),
        max_rounds=3,
    )
    context = AgentExecutionContext(
        settings=get_settings(),
        allowed_skill_names=("skill_a",),
        enabled_tool_names=("new_tool",),
    )

    result = await AgentExecutor().run(
        profile,
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=context,
        require_tool_first_round=True,
    )

    assert result.status == "completed"
    assert result.tools_called == ["load_skill", "new_tool"]
    assert [item.instruction for item in result.tool_results] == [True, False]
    assert result.tool_results[1].has_evidence is True
    assert result.has_context_evidence is True
    assert fresh.snapshot()["agentic"]["events"]["skill_tools_expanded"] == 1


def test_expand_skill_tools_adds_enabled_tool(monkeypatch):
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    monkeypatch.setattr(
        executor_module.registry,
        "get_tool",
        lambda name: SimpleNamespace(parameters={}),
    )
    monkeypatch.setattr(
        executor_module.registry,
        "get_tool_definitions_for",
        lambda names: [{"type": "function", "function": {"name": name}} for name in names],
    )
    state = SimpleNamespace(effective_tool_names=[], tool_definitions=[])
    context = AgentExecutionContext(
        settings=get_settings(),
        enabled_tool_names=("new_tool",),
    )

    AgentExecutor()._expand_skill_tools(
        state,
        context,
        '{"ok":true,"data":{"kind":"skill_instructions","tools":["new_tool"]}}',
    )

    assert state.effective_tool_names == ["new_tool"]
    assert state.tool_definitions == [{"type": "function", "function": {"name": "new_tool"}}]
    assert fresh.snapshot()["agentic"]["events"]["skill_tools_expanded"] == 1


def test_expand_skill_tools_rejects_unenabled_tool(monkeypatch):
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    monkeypatch.setattr(
        executor_module.registry,
        "get_tool",
        lambda name: SimpleNamespace(parameters={}),
    )
    monkeypatch.setattr(
        executor_module.registry,
        "get_tool_definitions_for",
        lambda names: [{"type": "function", "function": {"name": name}} for name in names],
    )
    state = SimpleNamespace(effective_tool_names=[], tool_definitions=[])
    context = AgentExecutionContext(
        settings=get_settings(),
        enabled_tool_names=("other_tool",),
    )

    AgentExecutor()._expand_skill_tools(
        state,
        context,
        '{"ok":true,"data":{"kind":"skill_instructions","tools":["new_tool"]}}',
    )

    assert state.effective_tool_names == []
    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_tool_rejected"] == 1
    assert "skill_tools_expanded" not in events


async def test_executor_loads_skill_and_uses_new_tool_in_same_turn(monkeypatch):
    load_definition = {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "load a skill",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    }
    data_definition = {
        "type": "function",
        "function": {
            "name": "new_tool",
            "description": "new data tool",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
    definitions = {"load_skill": load_definition, "new_tool": data_definition}
    parameters = {
        "load_skill": load_definition["function"]["parameters"],
        "new_tool": data_definition["function"]["parameters"],
    }
    same_turn = {"choices": [{"message": {"content": "", "tool_calls": [
        {
            "id": "call_1", "type": "function",
            "function": {"name": "load_skill", "arguments": '{"name":"skill_a"}'},
        },
        {
            "id": "call_2", "type": "function",
            "function": {"name": "new_tool", "arguments": "{}"},
        },
    ]}, "finish_reason": "tool_calls"}]}
    completions = _FakeCompletions([same_turn, _final_response("最终结论")])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        if call.function.name == "load_skill":
            content = '{"ok":true,"data":{"kind":"skill_instructions","tools":["new_tool"]}}'
        else:
            content = '{"ok":true,"data":{"value":1}}'
        return ToolResultInfo(tool_call_id=call.id, name=call.function.name, content=content)

    monkeypatch.setattr(
        registry,
        "get_tool_definitions_for",
        lambda names: [definitions[name] for name in names if name in definitions],
    )
    monkeypatch.setattr(
        registry,
        "get_tool_policy",
        lambda name: ToolPolicy(
            cache_ttl_seconds=0,
            evidence=name != "load_skill",
            budget="skill" if name == "load_skill" else "tool",
        ),
    )
    monkeypatch.setattr(
        registry,
        "get_tool",
        lambda name: SimpleNamespace(parameters=parameters[name]) if name in parameters else None,
    )
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    profile = AgentProfile(
        name="test-agent",
        display_name="测试 Agent",
        description="executor test",
        system_prompt="system",
        tool_names=("load_skill",),
        max_rounds=2,
    )
    context = AgentExecutionContext(
        settings=get_settings(),
        allowed_skill_names=("skill_a",),
        enabled_tool_names=("new_tool",),
    )

    result = await AgentExecutor().run(
        profile,
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=context,
        require_tool_first_round=True,
    )

    assert result.status == "completed"
    assert result.tools_called == ["load_skill", "new_tool"]
    assert [item.instruction for item in result.tool_results] == [True, False]
    assert result.tool_results[1].has_evidence is True
    assert len(completions.requests) == 2
