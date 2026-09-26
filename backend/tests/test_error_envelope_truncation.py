"""错误信封被截断后不得翻转成成功，工具自报 error_code 不得被丢弃。

两类回归的共同后果是「模型把失败读成成功」或「失败只剩一句通用文案」：

1. ``serialize_truncated_preview`` 硬编码 ``ok: true``，只有 ``ok is True`` 的信封
   走 ``bounded_document``。于是 ``{"ok": false, ...}`` 一旦超出上下文预算就被改写成
   ``{"ok": true, "data": {"preview": ...}}`` 或 ``{}``，而下游的 ``_error_message`` /
   ``result_error_message`` 只读外层 ``ok`` 与 ``error`` —— 读不到就不重试了。
2. ``serialize_result`` 把工具自报的 ``error_code`` 写死成 ``tool_reported_error``，
   导致 ``invalid_arguments`` 等分支在 events 层永不命中。
"""
import json

import pytest

from app.agentic.events import _tool_result_summary
from app.agentic.protocol import ToolResultInfo
from app.agentic.tools.serialization import (
    _DROPPED_RESULT,
    _MIN_DROPPED_RESULT_LEN,
    has_meaningful_tool_content,
    reported_error_code,
    serialize_context_result,
    serialize_context_results,
    serialize_result,
)

_ERROR = {
    "ok": False,
    "error": {
        "code": "upstream_unavailable",
        "message": "三张报表与关键指标全部取不到（income_sheet）；这是数据源暂时不可用，不是该公司没有财务数据",
        "retryable": True,
    },
    "data": {"code": "600519", "report_date": "2026半年报", "income": {"revenue": "907.03" * 400}},
}
_ERROR_CONTENT = json.dumps(_ERROR, ensure_ascii=False)

# 走 bounded_document 的成功信封：必须同时带 url 与 content。
_OK_CONTENT = json.dumps(
    {
        "ok": True,
        "data": {"url": "https://example.com/a", "title": "标题", "content": "正文" * 4000},
    },
    ensure_ascii=False,
)


def _decoded(content: str) -> object:
    if not content:
        return None
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return "<非法 JSON>"


class TestTruncatedErrorStaysAnError:
    @pytest.mark.parametrize("limit", [900, 500, 300, 200, 120, 80, 60, 40, 20, 11, 5, 4, 2])
    def test_ok_never_becomes_true(self, limit: int):
        assert len(_ERROR_CONTENT) > 900  # 保证这些 limit 都确实触发了截断
        out = serialize_context_result(_ERROR_CONTENT, limit)
        if not out:
            # 只有连最小标记 "null"（4 字符）都放不下时才留空。
            assert limit < _MIN_DROPPED_RESULT_LEN
            return
        decoded = _decoded(out)
        if decoded is None:
            # 最小标记：合法 JSON、不谎报成功、也不会被当成有效证据。
            assert out == _DROPPED_RESULT
            assert has_meaningful_tool_content(out) is False
            return
        assert isinstance(decoded, dict), f"limit={limit} 产出非法 JSON: {out!r}"
        assert decoded.get("ok") is False, f"limit={limit} 把失败翻成了 {out!r}"

    @pytest.mark.parametrize("limit", [900, 500, 300, 200, 120])
    def test_error_code_survives(self, limit: int):
        out = serialize_context_result(_ERROR_CONTENT, limit)
        decoded = _decoded(out)
        assert isinstance(decoded, dict)
        assert decoded["error"]["code"] == "upstream_unavailable"

    @pytest.mark.parametrize("limit", [900, 500, 300, 200, 120])
    def test_budget_is_respected(self, limit: int):
        assert len(serialize_context_result(_ERROR_CONTENT, limit)) <= limit

    def test_error_message_kept_when_it_fits(self):
        decoded = _decoded(serialize_context_result(_ERROR_CONTENT, 600))
        assert isinstance(decoded, dict)
        assert decoded["error"]["message"] == _ERROR["error"]["message"]

    def test_payload_is_shed_before_the_message(self):
        decoded = _decoded(serialize_context_result(_ERROR_CONTENT, 300))
        assert isinstance(decoded, dict)
        # 载荷先被压缩，错误信息仍然完整可读。
        assert decoded["error"]["message"] == _ERROR["error"]["message"]
        assert "preview" in decoded["data"]
        assert len(decoded["data"]["preview"]) < len(json.dumps(_ERROR["data"], ensure_ascii=False))

    def test_truncation_is_declared(self):
        decoded = _decoded(serialize_context_result(_ERROR_CONTENT, 300))
        assert isinstance(decoded, dict)
        assert decoded["meta"]["truncated"] is True

    def test_downstream_error_extractors_recover_the_reason(self):
        from app.modules.industry_chain.evidence import _error_message

        out = serialize_context_result(_ERROR_CONTENT, 300)
        assert "数据源暂时不可用" in _error_message(out)

    def test_truncated_error_is_not_meaningful_evidence(self):
        out = serialize_context_result(_ERROR_CONTENT, 300)
        assert has_meaningful_tool_content(out) is False

    def test_success_envelope_still_uses_the_bounded_document_path(self):
        # 不能为了修错误路径把成功路径一起改坏：正文信封仍保留来源与续读位置。
        out = serialize_context_result(_OK_CONTENT, 800)
        decoded = _decoded(out)
        assert isinstance(decoded, dict)
        assert decoded.get("ok") is True
        assert decoded["data"]["url"] == "https://example.com/a"
        assert decoded["meta"]["truncated"] is True

    def test_untouched_when_it_already_fits(self):
        assert serialize_context_result(_ERROR_CONTENT, len(_ERROR_CONTENT) + 10) == _ERROR_CONTENT

    def test_batch_budget_keeps_errors_as_errors(self):
        outs = serialize_context_results([_OK_CONTENT, _ERROR_CONTENT], 700)
        decoded = _decoded(outs[1])
        assert isinstance(decoded, dict)
        assert decoded.get("ok") is False
        assert decoded["error"]["code"] == "upstream_unavailable"


class TestReportedErrorCodePassthrough:
    def test_known_code_passes_through(self):
        assert reported_error_code({"ok": False, "error_code": "invalid_arguments"}) == "invalid_arguments"
        assert reported_error_code({"ok": False, "error_code": "upstream_unavailable"}) == "upstream_unavailable"

    def test_missing_code_falls_back(self):
        assert reported_error_code({"ok": False, "error": "boom"}) == "tool_reported_error"
        assert reported_error_code(["not", "a", "dict"]) == "tool_reported_error"

    @pytest.mark.parametrize("bad", ["Invalid Arguments", "has space", "UPPER", "a" * 65, "x-y", "", 42])
    def test_non_identifier_code_is_rejected(self, bad):
        assert reported_error_code({"ok": False, "error_code": bad}) == "tool_reported_error"

    def test_serialize_result_keeps_the_tool_code(self):
        content = serialize_result(
            {"ok": False, "error_code": "invalid_arguments", "error": "固定公式参数无效：x"}
        )
        payload = json.loads(content)
        assert payload["error"]["code"] == "invalid_arguments"

    def test_analyze_financials_style_result_reports_upstream_unavailable(self):
        # 我们修过的「五路全挂」路径：错误码必须原样到达事件层。
        content = serialize_result(
            {
                "code": "600519",
                "error_code": "upstream_unavailable",
                "error": "三张报表全部取不到。请改用其他来源，不要用相同参数重复调用。",
            }
        )
        assert json.loads(content)["error"]["code"] == "upstream_unavailable"


class TestReservedCodesAreNotImpersonated:
    """error_code 是工具返回值里的字段，不能冒充框架自己的保留码。

    保留码在事件层有专门语义：tool_budget_exceeded / duplicate_tool_call 会显示成
    「未实际执行 / 已跳过」。一旦透传，一次真的跑过的调用会被说成没跑，模型据此
    认为「我没调过」而重调，再吃一次拒绝。
    """

    @pytest.mark.parametrize(
        "code", ["tool_budget_exceeded", "duplicate_tool_call", "deadline_exceeded"]
    )
    def test_reserved_code_falls_back(self, code: str):
        assert reported_error_code({"ok": False, "error_code": code, "error": "x"}) == "tool_reported_error"

    @pytest.mark.parametrize("code", ["tool_budget_exceeded", "duplicate_tool_call"])
    def test_summary_is_not_skipped(self, code: str):
        content = serialize_result({"ok": False, "error_code": code, "error": "真实执行过"})
        summary = _tool_result_summary(
            ToolResultInfo(tool_call_id="c", name="web_fetch", content=content, is_error=True)
        )
        assert summary.status != "skipped"
        assert "未实际执行" not in summary.summary


class TestDiagnosticNamespaceIsNotShared:
    """``payload["data"]`` 也承载工具自报的原始返回，诊断必须有自己的命名空间。"""

    def test_contract_diagnostics_live_under_argument_error(self):
        from app.agentic.protocol import ToolCallInfo

        result = _run_stub(
            ToolCallInfo(
                id="c1",
                function={"name": "stub_contract", "arguments": '{"code": 600519}'},
            )
        )
        payload = json.loads(result.content)
        assert payload["data"]["argument_error"] == {
            "reason": "type_mismatch",
            "field": "code",
            "detail": "应为 string",
        }
        assert _tool_result_summary(result).summary == "参数类型不正确：code（应为 string）"

    def test_tool_reported_reason_never_becomes_a_diagnostic(self):
        from app.agentic.protocol import ToolCallInfo

        result = _run_stub(
            ToolCallInfo(id="c1", function={"name": "stub_spoof", "arguments": "{}"}),
        )
        payload = json.loads(result.content)
        # 工具自报的返回里带着 reason/field 也不该被当成契约校验诊断。
        assert payload["data"]["reason"] == "type_mismatch"
        assert "argument_error" not in payload["data"]
        summary = _tool_result_summary(result)
        assert summary.summary == "工具参数无效"
        assert "参数类型不正确" not in summary.summary


class TestUserVisibleSummaryForReportedCodes:
    async def test_tool_reported_invalid_arguments_is_not_generic(self):
        from app.agentic.protocol import ToolCallInfo

        result = await _execute(
            ToolCallInfo(id="c1", function={"name": "stub_reported", "arguments": "{}"}),
            name="stub_reported",
        )
        assert result.is_error is True
        summary = _tool_result_summary(result)
        assert summary.summary == "工具参数无效"
        assert summary.summary != "工具调用失败"

    async def test_upstream_unavailable_gets_its_own_label(self):
        from app.agentic.protocol import ToolCallInfo

        result = await _execute(
            ToolCallInfo(id="c1", function={"name": "stub_upstream", "arguments": "{}"}),
            name="stub_upstream",
        )
        assert _tool_result_summary(result).summary == "数据源暂不可用"

    async def test_unknown_reported_code_stays_generic(self):
        from app.agentic.protocol import ToolCallInfo

        result = await _execute(
            ToolCallInfo(id="c1", function={"name": "stub_weird", "arguments": "{}"}),
            name="stub_weird",
        )
        assert _tool_result_summary(result).summary == "工具调用失败"


def _run_stub(call):
    """同步跑一个桩工具：只需拿到 ToolResultInfo，不必进事件循环。"""
    import asyncio

    return asyncio.run(_execute(call, name=call.function.name))


async def _execute(call, *, name: str):
    from app.agentic.catalog import registry
    from app.agentic.tools.contracts import Tool

    payload_by_name = {
        "stub_reported": {"ok": False, "error_code": "invalid_arguments", "error": "输入无效"},
        "stub_upstream": {"ok": False, "error_code": "upstream_unavailable", "error": "上游挂了"},
        "stub_weird": {"ok": False, "error_code": "brand_new_code", "error": "未知"},
        "stub_spoof": {
            "ok": False,
            "error_code": "invalid_arguments",
            "error": "输入无效",
            "reason": "type_mismatch",
            "field": "code",
        },
    }

    if name == "stub_contract":

        async def contract_executor(code: str) -> dict:
            return {"code": code}

        tool = Tool(
            name=name,
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
            executor=contract_executor,
        )
    else:

        async def executor() -> dict:
            return payload_by_name[name]

        tool = Tool(
            name=name,
            description="测试用",
            parameters={"type": "object", "properties": {}},
            executor=executor,
        )
    registry.register_tool(tool)
    try:
        return await tool.execute(call)
    finally:
        registry._tools.pop(name, None)

    tool = Tool(name=name, description="测试用", parameters={"type": "object", "properties": {}}, executor=executor)
    registry.register_tool(tool)
    try:
        return await tool.execute(call)
    finally:
        registry._tools.pop(name, None)
