"""参数校验失败的界面诊断回归护栏。

修复前所有参数错误在界面上都是同一句「工具参数无效」：四类完全不同的问题
（缺参数 / 类型错 / 格式错 / 多余参数）对用户不可区分，于是「代码明明是对的
却报参数无效」这类问题无从定位。

核心约束是**受控**：message 完整回给模型（含模型自己传入的键名，便于自我纠正），
而界面文案只能由 reason 枚举 + 经白名单过滤的 field/detail 组成——模型输入的
键名若直接透传，任意字符串都会被打到界面上。
"""
import json

import pytest

from app.agentic.events import _tool_result_summary
from app.agentic.tools.contracts import Tool, invalid_arguments_data
from app.agentic.tools.validation import (
    ToolArgumentsError,
    _safe_names,
    validate_value,
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "pattern": r"^\d{6}$"},
        "period": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        "start_date": {"type": "string", "format": "date"},
        "prompt": {"type": "string", "minLength": 10},
        "codes": {"type": "array", "items": {"type": "string"}, "minItems": 2},
    },
    "required": ["code"],
    "additionalProperties": False,
}


def _raises(payload) -> ToolArgumentsError:
    with pytest.raises(ToolArgumentsError) as excinfo:
        validate_value(payload, _SCHEMA)
    return excinfo.value


class TestErrorCarriesControlledMetadata:
    def test_type_mismatch(self):
        error = _raises({"code": 600519})
        assert (error.reason, error.field) == ("type_mismatch", "code")
        assert error.detail == "应为 string"

    def test_missing_required(self):
        error = _raises({})
        assert error.reason == "missing_required"
        assert error.detail == "code"

    def test_pattern(self):
        error = _raises({"code": "123"})
        assert (error.reason, error.field) == ("pattern", "code")
        assert error.detail == ""

    def test_enum(self):
        error = _raises({"code": "600519", "period": "yearly"})
        assert error.reason == "enum"
        assert "daily" in error.detail and "monthly" in error.detail

    def test_unexpected_parameter(self):
        error = _raises({"code": "600519", "oops": 1})
        assert error.reason == "unexpected_parameter"
        assert error.detail == "oops"

    def test_min_length(self):
        error = _raises({"code": "600519", "prompt": "hi"})
        assert (error.reason, error.field) == ("min_length", "prompt")
        assert error.detail == "至少 10 字符"

    def test_min_items(self):
        error = _raises({"code": "600519", "codes": ["600519"]})
        assert error.reason == "min_items"
        assert error.detail == "至少 2 项"

    def test_minimum(self):
        error = _raises({"code": "600519", "limit": 0})
        assert (error.reason, error.field) == ("below_minimum", "limit")
        assert error.detail == "不得小于 1"

    def test_invalid_date(self):
        error = _raises({"code": "600519", "start_date": "2026/06/30"})
        assert error.reason == "invalid_date"
        assert error.field == "start_date"

    def test_field_never_contains_argument_prefix(self):
        # 界面文案里不该出现「参数.参数.code」这类路径残留。
        error = _raises({"code": 600519})
        assert "参数" not in error.field


class TestModelInputNeverReachesDetail:
    """安全护栏：模型输入的键名必须过标识符白名单才能进界面文案。"""

    def test_malicious_key_is_filtered(self):
        error = _raises({"code": "600519", "<script>alert(1)</script>": 1})
        assert "<script>" not in error.detail
        assert "alert" not in error.detail
        assert error.detail.endswith("个")  # 折叠成计数

    def test_filtered_name_still_reports_total(self):
        # 合法与非法键名混排时，合法的要展示，总数不能漏报。
        error = _raises({"code": "600519", "a": 1, "x-y": 2})
        assert error.detail == "a 等 2 个"

    def test_safe_names_helper(self):
        assert _safe_names(["ok_name"]) == "ok_name"
        assert _safe_names(["bad name"]) == "1 个"
        assert _safe_names([f"k{i}" for i in range(7)]).endswith("7 个")

    def test_message_still_carries_full_detail_for_the_model(self):
        # 脱敏只针对界面；模型仍要看到它自己传的键名才能自我纠正。
        error = _raises({"code": "600519", "oops": 1})
        assert "oops" in str(error)


class TestInvalidArgumentsData:
    def test_includes_reason_field_detail(self):
        data = invalid_arguments_data(_raises({"code": 600519}))
        assert data == {"reason": "type_mismatch", "field": "code", "detail": "应为 string"}

    def test_json_error_reports_reason_without_raw_text(self):
        # JSONDecodeError 的 message 含模型原文，只能透出枚举。
        data = invalid_arguments_data(json.JSONDecodeError("Expecting value", "doc", 0))
        assert data == {"reason": "invalid_json"}
        assert "Expecting" not in json.dumps(data)

    def test_unknown_error_returns_none(self):
        assert invalid_arguments_data(RuntimeError("boom")) is None


async def _summary_for(arguments: str, name: str = "stub_diag") -> str:
    async def echo_code(code: str) -> dict:
        return {"code": code}

    tool = Tool(
        name=name,
        description="测试用",
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string", "pattern": r"^\d{6}$"}},
            "required": ["code"],
        },
        executor=echo_code,
    )
    from app.agentic.catalog import registry

    registry.register_tool(tool)
    try:
        from app.agentic.protocol import ToolCallInfo

        result = await tool.execute(
            ToolCallInfo(id="c1", function={"name": name, "arguments": arguments})
        )
        return _tool_result_summary(result).summary
    finally:
        registry._tools.pop(name, None)


class TestUserVisibleSummary:
    async def test_each_failure_kind_is_distinguishable(self):
        # 这是本次修复的靶心：四类错误必须互不相同。
        summaries = await asyncio_gather_summaries()
        assert len(set(summaries)) == len(summaries) == 4

    async def test_summaries_are_specific(self):
        assert await _summary_for("{}") == "缺少必填参数：code"
        assert await _summary_for('{"code": 600519}') == "参数类型不正确：code（应为 string）"
        assert await _summary_for('{"code": "123"}') == "参数格式不正确：code"
        assert await _summary_for('{"code": "600519", "oops": 1}') == "包含未声明参数：oops"

    async def test_malicious_key_never_reaches_the_summary(self):
        summary = await _summary_for(
            '{"code": "600519", "<img src=x onerror=alert(1)>": 1}'
        )
        assert "<img" not in summary
        assert "alert" not in summary

    async def test_valid_call_is_not_an_error(self):
        from app.agentic.catalog import registry
        from app.agentic.protocol import ToolCallInfo

        async def echo_code(code: str) -> dict:
            return {"code": code}

        tool = Tool(
            name="stub_diag_ok",
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string", "pattern": r"^\d{6}$"}},
                "required": ["code"],
            },
            executor=echo_code,
        )
        registry.register_tool(tool)
        try:
            result = await tool.execute(
                ToolCallInfo(id="c1", function={"name": "stub_diag_ok", "arguments": '{"code": "600519"}'})
            )
            assert result.is_error is False
            assert _tool_result_summary(result).status == "success"
        finally:
            registry._tools.pop("stub_diag_ok", None)


async def asyncio_gather_summaries() -> list[str]:
    return [
        await _summary_for("{}"),
        await _summary_for('{"code": 600519}'),
        await _summary_for('{"code": "123"}'),
        await _summary_for('{"code": "600519", "oops": 1}'),
    ]
