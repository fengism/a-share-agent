"""工具参数 JSON 语法修复：只修语法，绝不改语义。

弱模型给出的参数经常"几乎合法"：套代码围栏、尾逗号、单引号、Python 字面量、
双重编码。此前一律落到"参数无效"让模型重来，白烧一轮工具配额。本文件同时锁住
修复能力与**安全边界**——字符串内容不得被改写、非对象结果不得被采用。
"""

from __future__ import annotations

import json

import pytest

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo
from app.agentic.tools import calls as calls_module
from app.agentic.tools.calls import prepare_tool_call
from app.agentic.tools.json_repair import load_arguments
from app.core.metrics import MetricsRegistry

_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string"}},
    "required": ["code"],
    "additionalProperties": False,
}


class _FakeTool:
    def __init__(self, parameters: dict) -> None:
        self.parameters = parameters


def _call(arguments: str) -> ToolCallInfo:
    return ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="fake_tool", arguments=arguments),
    )


def _use_tool(monkeypatch, schema: dict | None = None) -> None:
    tool = _FakeTool(schema or _SCHEMA)
    monkeypatch.setattr(registry, "get_tool", lambda name: tool if name == "fake_tool" else None)


@pytest.mark.parametrize(
    ("raw", "expected", "rule"),
    [
        ('{"code":"600519",}', {"code": "600519"}, "trailing_comma"),
        ('```json\n{"code":"600519"}\n```', {"code": "600519"}, "fence"),
        ("```\n{'code':'600519'}\n```", {"code": "600519"}, "fence+single_quotes"),
        ("{'code':'600519'}", {"code": "600519"}, "single_quotes"),
        ('{"code":"600519","n":None}', {"code": "600519", "n": None}, "python_literals"),
        ('"{\\"code\\":\\"600519\\"}"', {"code": "600519"}, "double_encoded"),
    ],
)
def test_syntax_repairs(raw: str, expected: dict, rule: str) -> None:
    parsed, applied = load_arguments(raw)
    assert parsed == expected
    assert applied == rule


def test_valid_json_is_not_rewritten() -> None:
    parsed, applied = load_arguments('{"code":"600519"}')
    assert parsed == {"code": "600519"}
    assert applied is None


def test_blank_arguments_are_an_empty_object() -> None:
    assert load_arguments("") == ({}, "empty")
    assert load_arguments(None) == ({}, "empty")


@pytest.mark.parametrize("raw", ["{not-json", "[1,2]", '{"code"}', '"just a string"'])
def test_unrepairable_or_non_object_stays_unparsed(raw: str) -> None:
    assert load_arguments(raw) == (None, None)


def test_string_contents_are_never_rewritten() -> None:
    """``True``/尾逗号出现在字符串里时必须原样保留，否则静默改坏取值。"""
    parsed, applied = load_arguments('{"a":"True","b":"x,}y",}')
    assert parsed == {"a": "True", "b": "x,}y"}
    assert applied == "trailing_comma"


def test_single_quote_repair_requires_quotation_free_text() -> None:
    """文本里已有双引号时不做单引号替换：无法区分子界符与字符串内的撇号。"""
    parsed, applied = load_arguments('{"a":1,"b":it\'s}')
    assert parsed is None
    assert applied is None


def test_prepare_tool_call_repairs_and_rewrites_arguments(monkeypatch) -> None:
    _use_tool(monkeypatch)
    prepared = prepare_tool_call(_call('{"code":"600519",}'))

    assert prepared.arguments == {"code": "600519"}
    # 回放给模型的历史、缓存键、Tool.execute 兜底都读这个字段：必须是修好的 JSON。
    assert json.loads(prepared.call.function.arguments) == {"code": "600519"}


def test_repair_rule_is_counted(monkeypatch) -> None:
    fresh = MetricsRegistry()
    monkeypatch.setattr(calls_module, "metrics", fresh)
    _use_tool(monkeypatch)

    prepare_tool_call(_call('{"code":"600519",}'))

    events = fresh.snapshot()["agentic"]["events"]
    assert events["tool_args_repaired:trailing_comma"] == 1


def test_schema_mismatch_after_repair_keeps_repaired_arguments(monkeypatch) -> None:
    """语法修好后即使 schema 不符，也要留下可解析的参数供 Tool.execute 报准确错误。"""
    _use_tool(monkeypatch)
    prepared = prepare_tool_call(_call('{"other":1,}'))

    assert prepared.arguments is None
    assert json.loads(prepared.call.function.arguments) == {"other": 1}


def test_unrepairable_arguments_keep_original_call(monkeypatch) -> None:
    _use_tool(monkeypatch)
    call = _call("{not-json")
    prepared = prepare_tool_call(call)

    assert prepared.call is call
    assert prepared.arguments is None


def test_pseudo_tool_call_arguments_are_repaired_too() -> None:
    """正文方言 ``fake_tool({'code':'600519',})`` 也要能被修复成对象。"""
    from app.agentic.tools.calls import extract_pseudo_tool_calls

    class _NamedTool:
        name = "fake_tool"

        def __init__(self) -> None:
            self.parameters = _SCHEMA

    class _Catalog:
        def list_tools(self):
            return [_NamedTool()]

        def get_tool(self, name: str):
            return _NamedTool() if name == "fake_tool" else None

    calls = extract_pseudo_tool_calls(
        "我先查一下 fake_tool({'code':'600519',})", _Catalog(), allowed_names={"fake_tool"}
    )

    assert [json.loads(call.function.arguments) for call in calls] == [{"code": "600519"}]
