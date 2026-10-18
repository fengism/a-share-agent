"""Tool-call normalization keeps the cheap path cheap and still unwraps envelopes."""

import json

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo
from app.agentic.tools.calls import normalize_wrapped_tool_call


class _FakeTool:
    def __init__(self, parameters: dict):
        self.parameters = parameters


_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string"}},
    "required": ["code"],
    "additionalProperties": False,
}


def _call(arguments: str, name: str = "fake_tool") -> ToolCallInfo:
    return ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name=name, arguments=arguments),
    )


def _use_tool(monkeypatch, schema: dict | None = None) -> None:
    tool = _FakeTool(schema or _SCHEMA)
    monkeypatch.setattr(registry, "get_tool", lambda name: tool if name == "fake_tool" else None)


def test_plain_arguments_skip_schema_validation(monkeypatch):
    _use_tool(monkeypatch)

    def fail(*args, **kwargs):
        raise AssertionError("coerce_arguments should not run for plain arguments")

    monkeypatch.setattr("app.agentic.tools.calls.coerce_arguments", fail)

    call = _call('{"code":"600519"}')
    assert normalize_wrapped_tool_call(call) is call


def test_wrapped_arguments_are_unwrapped(monkeypatch):
    _use_tool(monkeypatch)

    call = _call('{"arguments":{"code":"600519"}}')
    normalized = normalize_wrapped_tool_call(call)

    assert normalized is not call
    assert json.loads(normalized.function.arguments) == {"code": "600519"}


def test_nested_wrapped_arguments_are_unwrapped(monkeypatch):
    _use_tool(monkeypatch)

    call = _call('{"arguments":{"arguments":{"code":"600519"}}}')
    normalized = normalize_wrapped_tool_call(call)

    assert json.loads(normalized.function.arguments) == {"code": "600519"}


def test_declared_arguments_property_is_not_treated_as_an_envelope(monkeypatch):
    _use_tool(
        monkeypatch,
        {
            "type": "object",
            "properties": {"arguments": {"type": "object"}},
            "required": ["arguments"],
            "additionalProperties": False,
        },
    )

    call = _call('{"arguments":{"code":"600519"}}')
    assert normalize_wrapped_tool_call(call) is call


def test_invalid_json_is_left_untouched(monkeypatch):
    _use_tool(monkeypatch)

    call = _call("{not-json")
    assert normalize_wrapped_tool_call(call) is call
