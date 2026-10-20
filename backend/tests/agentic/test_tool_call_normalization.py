"""参数拆壳：模型把参数多包一层时，生产路径必须还原成 schema 形状。

历史上这些断言挂在一个从未被调用的 ``normalize_wrapped_tool_call()`` 上，等于
「有测试、无覆盖」——拆壳的真实执行者是 ``prepare_tool_call()``（它同时负责单次解析
与类型强制），所以这里直接锁生产函数。

为什么重要：证据、工具缓存键、回放给模型的历史消息都读 ``function.arguments``。
不解包时证据里的 ``code`` 是空串，产业链修复循环据此判定「财务未执行」并无限重试。
"""

from __future__ import annotations

import json

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo
from app.agentic.tools.calls import prepare_tool_call

_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string"}},
    "required": ["code"],
    "additionalProperties": False,
}


class _FakeTool:
    def __init__(self, parameters: dict) -> None:
        self.parameters = parameters


def _call(arguments: str, name: str = "fake_tool") -> ToolCallInfo:
    return ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name=name, arguments=arguments),
    )


def _use_tool(monkeypatch, schema: dict | None = None) -> None:
    tool = _FakeTool(schema or _SCHEMA)
    monkeypatch.setattr(registry, "get_tool", lambda name: tool if name == "fake_tool" else None)


def test_plain_arguments_are_not_rewritten(monkeypatch):
    _use_tool(monkeypatch)
    call = _call('{"code":"600519"}')
    prepared = prepare_tool_call(call)

    assert prepared.call is call
    assert prepared.arguments == {"code": "600519"}


def test_wrapped_arguments_are_unwrapped(monkeypatch):
    _use_tool(monkeypatch)
    prepared = prepare_tool_call(_call('{"arguments":{"code":"600519"}}'))

    assert json.loads(prepared.call.function.arguments) == {"code": "600519"}
    assert prepared.arguments == {"code": "600519"}


def test_nested_wrapped_arguments_are_unwrapped(monkeypatch):
    _use_tool(monkeypatch)
    prepared = prepare_tool_call(_call('{"arguments":{"arguments":{"code":"600519"}}}'))

    assert json.loads(prepared.call.function.arguments) == {"code": "600519"}


def test_every_wire_envelope_key_is_unwrapped(monkeypatch):
    _use_tool(monkeypatch)
    for key in ("arguments", "parameters", "input", "args"):
        prepared = prepare_tool_call(_call(json.dumps({key: {"code": "600519"}})))
        assert prepared.arguments == {"code": "600519"}, key


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
    prepared = prepare_tool_call(_call('{"arguments":{"code":"600519"}}'))

    assert prepared.arguments == {"arguments": {"code": "600519"}}


def test_invalid_json_defers_to_tool_execute(monkeypatch):
    _use_tool(monkeypatch)
    call = _call("{not-json")
    prepared = prepare_tool_call(call)

    assert prepared.call is call
    assert prepared.arguments is None


def test_unknown_tool_defers_to_tool_execute(monkeypatch):
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    call = _call('{"code":"600519"}', name="missing_tool")
    prepared = prepare_tool_call(call)

    assert prepared.call is call
    assert prepared.arguments is None
