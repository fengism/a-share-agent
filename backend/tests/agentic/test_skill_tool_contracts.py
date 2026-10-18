"""Skill matching and tool-registration contracts."""

import json
from types import SimpleNamespace

import pytest

from app.agentic.catalog import CapabilityCatalog
from app.agentic.protocol import ToolCallFunction, ToolCallInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.skills.contracts import Skill
from app.agentic.tools.calls import (
    extract_markup_tool_calls,
    extract_pseudo_tool_calls,
    prepare_tool_call,
)
from app.agentic.tools.contracts import Tool


async def _fake_executor(code: str = ""):
    return {"code": code}


async def _second_executor():
    return {}


def _skill(**overrides) -> Skill:
    values = {
        "name": "test_skill",
        "description": "test",
        "triggers": ("test",),
        "activation_keywords": ("pe", "估值"),
        "tool_names": ("fake_tool",),
        "rules": ("use fake_tool",),
    }
    values.update(overrides)
    return Skill(**values)


def _catalog() -> CapabilityCatalog:
    catalog = CapabilityCatalog()
    catalog.register_tool(Tool(
        name="fake_tool",
        description="test tool",
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        executor=_fake_executor,
    ))
    return catalog


def test_skill_ascii_keyword_uses_word_boundary():
    skill = _skill()

    assert skill.matches("请分析 PE 估值")
    assert not skill.matches("apple 公司")


def test_skill_chinese_keyword_uses_substring():
    skill = _skill()

    assert skill.matches("最新估值是多少")
    assert skill.matches_normalized("最新估值是多少")


def test_tool_definitions_preserve_registry_order():
    catalog = _catalog()
    catalog.register_tool(Tool(
        name="second_tool",
        description="second",
        parameters={"type": "object", "properties": {}},
        executor=_second_executor,
    ))

    definitions = catalog.get_tool_definitions_for(["second_tool", "fake_tool"])

    assert [item["function"]["name"] for item in definitions] == ["fake_tool", "second_tool"]


def test_pseudo_tool_calls_are_extracted_and_cached():
    catalog = _catalog()
    text = '请调用 fake_tool("600519")'

    first = extract_pseudo_tool_calls(text, catalog)
    second = extract_pseudo_tool_calls(text, catalog)

    assert len(first) == 1
    assert first[0].function.name == "fake_tool"
    assert json.loads(first[0].function.arguments) == {"code": "600519"}
    assert len(second) == 1


def test_markup_tool_calls_are_extracted():
    catalog = _catalog()
    text = '<tool_calls>[{"name":"fake_tool","arguments":{"code":"600519"}}]</tool_calls>'

    calls = extract_markup_tool_calls(text, catalog)

    assert len(calls) == 1
    assert calls[0].function.name == "fake_tool"
    assert json.loads(calls[0].function.arguments) == {"code": "600519"}


def test_all_registered_tools_are_covered_by_a_skill():
    from app.agentic.catalog import registry
    from app.agentic_integration.bootstrap import register_all_capabilities

    register_all_capabilities()

    assert registry.validate_skill_coverage() == []


def test_register_skill_catalog_rolls_back_on_failure(monkeypatch):
    from app.agentic_integration.skills import catalog as skill_catalog

    target = _catalog()
    valid = _skill(name="valid_skill")
    invalid = _skill(name="invalid_skill", tool_names=("missing_tool",))
    monkeypatch.setattr(skill_catalog, "list_builtin_skills", lambda: [valid, invalid])

    with pytest.raises(ValueError):
        skill_catalog.register_skill_catalog(target)

    assert target.list_skills() == []


def test_prepare_tool_call_parses_plain_arguments_once(monkeypatch):
    tool = _catalog().get_tool("fake_tool")
    monkeypatch.setattr(
        "app.agentic.tools.calls.registry.get_tool",
        lambda name: tool if name == "fake_tool" else None,
    )
    call = ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="fake_tool", arguments='{"code":"600519"}'),
    )

    prepared = prepare_tool_call(call)

    assert prepared.call.function.arguments == '{"code":"600519"}'
    assert prepared.arguments == {"code": "600519"}


def test_prepare_tool_call_unwraps_envelope(monkeypatch):
    tool = _catalog().get_tool("fake_tool")
    monkeypatch.setattr(
        "app.agentic.tools.calls.registry.get_tool",
        lambda name: tool if name == "fake_tool" else None,
    )
    call = ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(
            name="fake_tool",
            arguments='{"arguments":{"code":"600519"}}',
        ),
    )

    prepared = prepare_tool_call(call)

    assert json.loads(prepared.call.function.arguments) == {"code": "600519"}
    assert prepared.arguments == {"code": "600519"}


def test_prepare_tool_call_defers_invalid_arguments_to_tool_execute(monkeypatch):
    tool = _catalog().get_tool("fake_tool")
    monkeypatch.setattr(
        "app.agentic.tools.calls.registry.get_tool",
        lambda name: tool if name == "fake_tool" else None,
    )
    call = ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="fake_tool", arguments="{not-json"),
    )

    prepared = prepare_tool_call(call)

    assert prepared.arguments is None


async def test_tool_execute_uses_prepared_arguments():
    catalog = _catalog()
    tool = catalog.get_tool("fake_tool")
    assert tool is not None
    call = ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="fake_tool", arguments="{not-json"),
    )

    context = AgentExecutionContext(
        settings=SimpleNamespace(chat_tool_timeout_seconds=10),
    )
    result = await tool.execute(call, execution_context=context, arguments={"code": "600519"})

    assert result.is_error is False
    assert json.loads(result.content)["data"] == {"code": "600519"}
