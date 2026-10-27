"""Core AgentExecutor loop: tool round, dedupe, reasoning budget, failure labels."""

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import _MAX_REPLAY_REASONING_CHARACTERS, AgentExecutor
from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo, ToolResultInfo
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


async def test_assistant_message_cleans_pseudo_tool_markup(monkeypatch):
    """验证助手消息中混杂的伪工具调用标记在回放时被净化，避免历史污染。"""
    markup_content = "<tool_call>\n{\"name\": \"fake_tool\", \"arguments\": {}}\n</tool_call>"
    response_with_markup = {
        "choices": [{
            "message": {
                "content": markup_content,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": _FAKE_TOOL, "arguments": "{}"},
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }
    completions = _FakeCompletions([response_with_markup, _final_response()])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    assistant_messages = [
        message
        for message in completions.requests[1]["messages"]
        if message.get("role") == "assistant" and message.get("tool_calls")
    ]
    assert len(assistant_messages) == 1
    # 伪标记被剥离，避免污染后续轮次 prompt
    assert assistant_messages[0].get("content") is None
    assert any("模型以正文形式输出了工具调用标记" in warning for warning in result.warnings)


def _distinct_argument_tool_calls() -> dict:
    def call(call_id: str, arguments: str) -> dict:
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": _FAKE_TOOL, "arguments": arguments},
        }

    return {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [call("call_1", '{"a":1}'), call("call_2", '{"b":2}')],
            },
            "finish_reason": "tool_calls",
        }],
    }


async def test_local_tool_execution_is_concurrent_even_when_provider_flag_is_false(monkeypatch):
    """``parallel_tool_calls`` 描述模型能否一次发多个调用，不能把本地执行串行化。

    聚合/自建网关该能力位为 False，此前一轮内多个工具调用被逐个 await，
    整轮延迟按调用数线性放大。
    """
    import asyncio

    completions = _FakeCompletions([_distinct_argument_tool_calls(), _final_response()])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)

    # 用事件而不是 sleep 判定并发：两个调用都必须先"启动"并等待，释放才会发生。
    # 串行执行时第二个调用永远等不到启动，release 只被消费一次，测试以超时失败。
    started: list[str] = []
    running: set[str] = set()
    both_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        started.append(call.id)
        running.add(call.id)
        if len(running) == 2:
            both_started.set()
        try:
            await asyncio.wait_for(both_started.wait(), timeout=2.0)
        except asyncio.TimeoutError:  # pragma: no cover - 串行时会走到这里
            raise AssertionError("工具调用被串行执行：第二个调用未与第一个并发启动") from None
        release.set()
        running.discard(call.id)
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content='{"ok":true,"data":{"value":1}}',
            is_error=False,
        )

    monkeypatch.setattr(
        registry,
        "get_tool_definitions_for",
        lambda names: [_TOOL_DEFINITION] if _FAKE_TOOL in names else [],
    )
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)

    capabilities = replace(DEFAULT_LLM_CAPABILITIES, parallel_tool_calls=False)
    result = await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        _FakeClient(capabilities),
        "fake-model",
        execution_context=_context(),
        require_tool_first_round=True,
    )

    # 两个调用都进入过"等待放行"状态，说明它们在同一批次里并发执行。
    # 串行实现下第二个调用永远等不到启动，这里会直接失败并指明原因。
    assert both_started.is_set(), f"工具调用未并发执行，实际启动顺序：{started}"
    assert release.is_set()
    assert result.status == "completed"
    assert len(started) == 2


def _content_only_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content, "tool_calls": []}, "finish_reason": "stop"}]}


async def test_pseudo_tool_call_fallback_is_counted(monkeypatch):
    """模型不返回原生 tool_calls、靠正文方言发起调用时必须可观测。"""
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    calls: list[list[ToolCallInfo]] = [
        [
            ToolCallInfo(
                id="pseudo_0",
                type="function",
                function=ToolCallFunction(name=_FAKE_TOOL, arguments="{}"),
            )
        ],
        [],  # 后续轮次没有方言调用
    ]
    monkeypatch.setattr(
        executor_module,
        "extract_pseudo_tool_calls",
        lambda *args, **kwargs: calls.pop(0) if calls else [],
    )
    completions = _FakeCompletions([
        _content_only_response("fake_tool()"),
        _final_response(),
        _final_response(),
    ])
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    _install_registry(monkeypatch, [('{"ok":true,"data":{"value":1}}', False)])

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
    events = fresh.snapshot()["agentic"]["events"]
    assert events["agent_pseudo_tool_call"] == 1
