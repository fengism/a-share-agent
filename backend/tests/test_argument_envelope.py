"""模型多包一层参数外壳（{"arguments": {"code": ...}}）的回归护栏。

线格式的参数字段名就是 arguments，模型会把它回显进参数体。修复前这会命中
「缺少必填参数：code」-> invalid_arguments -> 界面显示「工具参数无效」，而线格式
又持续提示模型这么包，于是稳定复现为「参数解析一直失败」。

三处必须同时正确，缺一处都会让问题以别的形态回来：
1. 执行侧解包，否则工具直接报参数无效；
2. tool_call 事件解包，否则证据里的 code 是空串，产业链修复循环判定「财务
   未执行」并反复建任务；缓存键也会打不中；
3. schema 真声明了 arguments 参数的工具不能被误拆。
"""
import json
import time

import pytest

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import AgentExecutor, _ExecutionState
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.calls import normalize_wrapped_tool_call
from app.agentic.tools.contracts import Tool
from app.agentic.tools.validation import ToolArgumentsError, coerce_arguments
from app.infrastructure.llm.capabilities import DEFAULT_LLM_CAPABILITIES

_CODE_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string", "pattern": r"^\d{6}$"}},
    "required": ["code"],
}


@pytest.fixture
def code_tool():
    """注册一个最小工具，测试结束还原 registry。"""

    async def echo_code(code: str) -> dict:
        return {"code": code}

    tool = Tool(
        name="stub_echo_code",
        description="测试用",
        parameters=dict(_CODE_SCHEMA),
        executor=echo_code,
    )
    registry.register_tool(tool)
    yield tool
    registry._tools.pop("stub_echo_code", None)


def _call(arguments: str, name: str = "stub_echo_code") -> ToolCallInfo:
    return ToolCallInfo(id="c1", function={"name": name, "arguments": arguments})


class TestCoerceArguments:
    def test_unwraps_arguments_envelope(self):
        wrapped = {"arguments": {"code": "600519"}}
        assert coerce_arguments(wrapped, _CODE_SCHEMA) == {"code": "600519"}

    @pytest.mark.parametrize("key", ["parameters", "input", "args"])
    def test_unwraps_other_envelope_names(self, key):
        assert coerce_arguments({key: {"code": "600519"}}, _CODE_SCHEMA) == {"code": "600519"}

    def test_returns_original_when_already_valid(self):
        original = {"code": "600519"}
        assert coerce_arguments(original, _CODE_SCHEMA) is original

    def test_does_not_unwrap_declared_arguments_property(self):
        # 真声明了 arguments 参数的工具，拆了就是改语义。
        schema = {
            "type": "object",
            "properties": {"arguments": {"type": "object"}},
            "required": ["arguments"],
            "additionalProperties": False,
        }
        payload = {"arguments": {"x": 1}}
        assert coerce_arguments(payload, schema) == payload

    def test_does_not_unwrap_when_envelope_shares_the_bread(self):
        # 外壳只是多出来的键之一时不是包装形态，原样报错。
        with pytest.raises(ToolArgumentsError) as excinfo:
            coerce_arguments({"arguments": {"code": "600519"}, "extra": 1}, _CODE_SCHEMA)
        assert "缺少必填参数" in str(excinfo.value)

    def test_does_not_unwrap_non_object_inner(self):
        with pytest.raises(ToolArgumentsError):
            coerce_arguments({"arguments": "600519"}, _CODE_SCHEMA)

    def test_raises_original_error_when_there_is_no_envelope(self):
        with pytest.raises(ToolArgumentsError) as excinfo:
            coerce_arguments({"wrong": 1}, _CODE_SCHEMA)
        assert "缺少必填参数：code" in str(excinfo.value)

    def test_reports_inner_error_after_unwrapping(self):
        with pytest.raises(ToolArgumentsError) as excinfo:
            coerce_arguments({"arguments": {"code": "123"}}, _CODE_SCHEMA)
        assert "格式不正确" in str(excinfo.value)

    def test_wrong_field_name_is_not_silently_unwrapped(self):
        """模型把 parameters 当成真实参数名传进来时，必须照实报错，不能解包成成功。

        这里刻意用「有 additionalProperties=False 但没有必填项」的 schema：首个错误
        是「包含未声明参数」而不是「缺少必填参数」，所以不满足解包的前提。
        """
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "additionalProperties": False,
        }
        with pytest.raises(ToolArgumentsError) as excinfo:
            coerce_arguments({"parameters": {"code": "600519"}}, schema)
        assert excinfo.value.reason == "unexpected_parameter"

    def test_unwraps_when_only_required_field_is_missing(self):
        # 与上面相反：缺必填参数才是「多包了一层外壳」的样子，仍然要解包。
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        }
        assert coerce_arguments({"parameters": {"code": "600519"}}, schema) == {"code": "600519"}

    def test_unwraps_nested_envelopes(self):
        payload = {"arguments": {"arguments": {"code": "600519"}}}
        assert coerce_arguments(payload, _CODE_SCHEMA) == {"code": "600519"}


class TestToolExecute:
    async def test_accepts_wrapped_arguments(self, code_tool):
        result = await code_tool.execute(_call(json.dumps({"arguments": {"code": "600519"}})))
        payload = json.loads(result.content)
        assert result.is_error is False
        assert payload["data"] == {"code": "600519"}

    async def test_still_rejects_genuinely_bad_arguments(self, code_tool):
        result = await code_tool.execute(_call(json.dumps({"wrong": 1})))
        payload = json.loads(result.content)
        assert result.is_error is True
        assert payload["error"]["code"] == "invalid_arguments"
        assert "缺少必填参数：code" in payload["error"]["message"]

    async def test_still_rejects_non_json_arguments(self, code_tool):
        result = await code_tool.execute(_call("not json"))
        payload = json.loads(result.content)
        assert result.is_error is True
        assert payload["error"]["code"] == "invalid_arguments"

    async def test_rejects_wrapper_with_broken_inner_arguments(self, code_tool):
        result = await code_tool.execute(_call(json.dumps({"arguments": {"code": "123"}})))
        payload = json.loads(result.content)
        assert result.is_error is True
        assert payload["error"]["code"] == "invalid_arguments"
        assert "格式不正确" in payload["error"]["message"]


class TestNormalizeWrappedToolCall:
    def test_returns_clean_arguments(self, code_tool):
        wrapped = _call(json.dumps({"arguments": {"code": "688836"}}))
        assert json.loads(normalize_wrapped_tool_call(wrapped).function.arguments) == {
            "code": "688836"
        }

    def test_keeps_already_clean_call(self, code_tool):
        clean = _call(json.dumps({"code": "688836"}))
        assert normalize_wrapped_tool_call(clean) is clean

    def test_keeps_unknown_tool_unchanged(self):
        unknown = _call(json.dumps({"arguments": {"code": "688836"}}), name="no_such_tool")
        assert normalize_wrapped_tool_call(unknown) is unknown

    def test_keeps_call_when_inner_also_fails_validation(self, code_tool):
        broken = _call(json.dumps({"arguments": {"code": "123"}}))
        assert normalize_wrapped_tool_call(broken) is broken

    def test_keeps_non_json_arguments(self, code_tool):
        # 让执行侧抛 JSONDecodeError，消息里带上原始解析错误。
        broken = _call("not json")
        assert normalize_wrapped_tool_call(broken) is broken


class TestExecutorEmitsNormalizedArguments:
    """事件源头不解包，证据里的 code 就会是空串。"""

    async def test_tool_call_event_and_history_carry_real_arguments(self, code_tool):
        executor = AgentExecutor()
        profile = AgentProfile(
            name="envelope_tester",
            display_name="外壳测试",
            description="测试",
            system_prompt="prompt",
            tool_names=("stub_echo_code",),
        )
        state = _ExecutionState(
            started_at=time.monotonic(),
            messages=[],
            effective_tool_names=list(profile.tool_names),
            tool_definitions=[],
            tool_cache=SharedToolCache(),
            max_tool_context_characters=8000,
        )
        events: list[AgentEvent] = []

        async def emit(event: AgentEvent) -> None:
            events.append(event)

        await executor._execute_tool_calls(
            profile,
            state,
            [_call(json.dumps({"arguments": {"code": "688836"}}))],
            "",
            emit,
            None,
            0,
            DEFAULT_LLM_CAPABILITIES,
        )

        tool_call_events = [event for event in events if event.type == "tool_call"]
        assert len(tool_call_events) == 1
        emitted = tool_call_events[0].tool_call
        assert json.loads(emitted.function.arguments) == {"code": "688836"}

        # 回放给模型的历史消息也要是解包后的形状，否则模型会继续照抄外壳。
        assistant = next(m for m in state.messages if m.get("role") == "assistant")
        assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {
            "code": "688836"
        }

        # 解包后工具真的执行成功，而不是停在 invalid_arguments。
        tool_results = [event for event in events if event.type == "tool_result"]
        assert len(tool_results) == 1
        assert tool_results[0].tool_result.is_error is False
