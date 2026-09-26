"""工具调用标记泄漏与预算耗尽的回归护栏。

真实事故：用户在 chat 里收到的「回答」是一串

    <｜DSML｜tool_calls> <｜DSML｜invoke name="analyze_financials"> \
<｜DSML｜parameter name="arguments">{"code": "002432"}</｜DSML｜parameter> </｜DSML｜invoke> …
    </｜DSML｜tool_calls>

用户看到的现象是「提示上下文预算不足，然后没有输出」。根因有三层，缺一层就会换个
形态复发：

1. 认不出来：``extract_pseudo_tool_calls`` 只认 ``tool_name(...)``，DeepSeek 这类
   模型把调用写成正文标记时既没被执行、也没被拦下，整段标记当成最终结论流出去；
2. 擦不干净：认不出的方言（含流式增量、被截断的半截标记）必须从回答里移除，
   绝不能让标记出现在用户面前；
3. 不会收敛：工具结果的上下文预算耗尽后，执行侧已经拒绝对话工具，却仍把工具定义
   摆给模型，模型宁可再调一次也不作答，于是一轮轮烧到 max_rounds 耗尽。
"""
import json
import time

import pytest

from app.agentic.agents.contracts import (
    AgentExecutionResult,
    AgentProfile,
    ToolExecutionSummary,
)
from app.agentic.agents.executor import (
    _TOOL_CONTEXT_WARNING,
    _TOOL_MARKUP_WARNING,
    AgentExecutor,
    _ExecutionState,
)
from app.agentic.catalog import registry
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.calls import (
    ToolCallMarkupStreamFilter,
    extract_pseudo_tool_calls,
    has_tool_call_markup,
    strip_tool_call_markup,
)
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.configuration.schema import Settings
from app.infrastructure.llm.tool_calling import LLMTurn
from app.modules.chat.orchestrator import _summarize_failure_reasons

LEAKED_DSML = (
    "现在让我获取九安医疗的财务数据，以及查看美的集团和电投能源的机构一致预期数据。"
    '<｜DSML｜tool_calls> <｜DSML｜invoke name="analyze_financials"> '
    '<｜DSML｜parameter name="arguments" string="false">{"code": "002432"}</｜DSML｜parameter> '
    "</｜DSML｜invoke> \n"
    '<｜DSML｜invoke name="get_stock_valuation_detail"> '
    '<｜DSML｜parameter name="arguments" string="false">{"code": "002170"}</｜DSML｜parameter> '
    "</｜DSML｜invoke> \n"
    "</｜DSML｜tool_calls>"
)


class _ScriptedExecutor(AgentExecutor):
    """用脚本轮次替代真实 LLM：这里要测的是执行引擎如何处理这些轮次。"""

    def __init__(self, turns: list[LLMTurn]) -> None:
        self.turns = list(turns)
        self.seen_tool_definitions: list[tuple[dict, ...]] = []

    async def _complete_turn(self, llm_client, **kwargs) -> LLMTurn:  # type: ignore[override]
        self.seen_tool_definitions.append(tuple(kwargs.get("tool_definitions") or ()))
        assert self.turns, "脚本轮次已用尽"
        return self.turns.pop(0)


@pytest.fixture
def echo_tool():
    """注册一个最小工具并记录真实执行次数，测试结束还原 registry。"""
    executed: list[str] = []

    async def echo(code: str = "") -> dict:
        executed.append(code)
        return {"code": code}

    tool = Tool(
        name="stub_markup_echo",
        description="测试用",
        parameters={"type": "object", "properties": {"code": {"type": "string"}}},
        executor=echo,
        policy=ToolPolicy(cache_ttl_seconds=0),
    )
    registry.register_tool(tool)
    yield tool, executed
    registry._tools.pop(tool.name, None)


def _profile(tool_names: tuple[str, ...] = ()) -> AgentProfile:
    return AgentProfile(
        name="markup_tester",
        display_name="标记测试",
        description="测试",
        system_prompt="prompt",
        tool_names=tool_names,
        max_rounds=3,
    )


class TestExtractMarkupToolCalls:
    def test_reads_dsml_invoke_blocks(self, echo_tool):
        tool, _ = echo_tool
        text = LEAKED_DSML.replace("analyze_financials", tool.name).replace(
            "get_stock_valuation_detail", tool.name
        )
        calls = extract_pseudo_tool_calls(text, registry, allowed_names=[tool.name])
        assert [call.function.name for call in calls] == [tool.name, tool.name]
        # 线格式的参数字段名就是 arguments，模型会把它一并回显：拆壳后才是真实参数。
        assert [json.loads(call.function.arguments) for call in calls] == [
            {"code": "002432"},
            {"code": "002170"},
        ]

    def test_keeps_envelope_when_schema_declares_that_parameter(self, echo_tool):
        async def echo_arguments(arguments: dict) -> dict:
            return arguments

        declared = Tool(
            name="stub_declared_arguments",
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"arguments": {"type": "object"}},
                "required": ["arguments"],
                "additionalProperties": False,
            },
            executor=echo_arguments,
        )
        registry.register_tool(declared)
        try:
            text = (
                '<｜DSML｜invoke name="stub_declared_arguments">'
                '<｜DSML｜parameter name="arguments">{"code": "600519"}</｜DSML｜parameter>'
                "</｜DSML｜invoke>"
            )
            calls = extract_pseudo_tool_calls(text, registry, allowed_names=[declared.name])
            # 真声明了 arguments 参数的工具，拆了就是改语义。
            assert [json.loads(call.function.arguments) for call in calls] == [
                {"arguments": {"code": "600519"}}
            ]
        finally:
            registry._tools.pop(declared.name, None)

    def test_reads_tagged_json_block(self, echo_tool):
        tool, _ = echo_tool
        text = f'<tool_call>{{"name": "{tool.name}", "arguments": {{"code": "600519"}}}}</tool_call>'
        calls = extract_pseudo_tool_calls(text, registry, allowed_names=[tool.name])
        assert [(call.function.name, json.loads(call.function.arguments)) for call in calls] == [
            (tool.name, {"code": "600519"})
        ]

    def test_skips_tools_outside_the_allowed_set(self, echo_tool):
        assert extract_pseudo_tool_calls(LEAKED_DSML, registry, allowed_names=[]) == []

    def test_returns_nothing_for_plain_prose(self, echo_tool):
        assert extract_pseudo_tool_calls("贵州茅台营收微增 1.47%。", registry) == []


class TestStripToolCallMarkup:
    def test_removes_closed_dsml_block_and_keeps_narration(self, echo_tool):
        assert strip_tool_call_markup(LEAKED_DSML) == (
            "现在让我获取九安医疗的财务数据，以及查看美的集团和电投能源的机构一致预期数据。"
        )

    def test_removes_truncated_markup_to_the_end(self):
        # 模型被截断时标记没有闭合：半截标记比没有输出更糟，宁可整段丢掉。
        assert strip_tool_call_markup('结论：<｜DSML｜tool_calls> <｜DSML｜invoke name="web_search">') == "结论："

    def test_removes_tagged_json_block(self):
        assert strip_tool_call_markup('<tool_call>{"name": "web_search"}</tool_call>') == ""

    def test_leaves_benign_prose_untouched(self):
        benign = "可以用 analyze_financials 工具查看，涨幅<5% 的标的也要留意。"
        assert strip_tool_call_markup(benign) == benign
        assert has_tool_call_markup(benign) is False


class TestToolCallMarkupStreamFilter:
    def test_plain_text_is_streamed_incrementally(self):
        plain = "贵州茅台营收微增 1.47%，毛利率 89.56%，估值处于历史低位（PE 3.8% 分位）。"
        stream_filter = ToolCallMarkupStreamFilter()
        chunks = [stream_filter.feed(plain[i:i + 3]) for i in range(0, len(plain), 3)]
        # 缓冲到流末尾等于取消流式：正常正文必须照旧逐块推出去。
        assert "".join(chunks) == plain
        assert stream_filter.flush() == ""

    def test_markup_split_across_chunks_never_leaks(self):
        text = "结论如下。" + LEAKED_DSML.replace("\n", "") + "补充说明。"
        stream_filter = ToolCallMarkupStreamFilter()
        streamed = "".join(stream_filter.feed(text[i:i + 5]) for i in range(0, len(text), 5))
        assert "DSML" not in streamed
        assert "<" not in streamed
        assert streamed.startswith("结论如下。")
        assert streamed.endswith("补充说明。")
        assert stream_filter.flush() == ""

    def test_markup_split_across_arbitrary_chunk_sizes(self):
        text = "结论如下。" + LEAKED_DSML.replace("\n", "") + "补充说明。"
        for size in (1, 2, 3, 7, 13, 64):
            stream_filter = ToolCallMarkupStreamFilter()
            streamed = "".join(
                stream_filter.feed(text[i:i + size]) for i in range(0, len(text), size)
            )
            streamed += stream_filter.flush()
            assert "DSML" not in streamed, size
            assert "<" not in streamed, size
            assert "结论如下。" in streamed and "补充说明。" in streamed, size

    def test_unclosed_markup_drops_the_rest(self):
        text = '结论：<｜DSML｜tool_calls> <｜DSML｜invoke name="web_search">'
        stream_filter = ToolCallMarkupStreamFilter()
        emitted = "".join(stream_filter.feed(text[i:i + 4]) for i in range(0, len(text), 4))
        assert emitted + stream_filter.flush() == "结论："


class TestExecutorDoesNotLeakMarkup:
    """标记要么被执行、要么被移除，绝不能作为结论返回（用户「没有输出」的真实成因）。"""

    async def test_dsml_markup_is_executed_instead_of_being_the_answer(self, echo_tool):
        tool, executed = echo_tool
        leaked = (
            "让我调用工具。"
            '<｜DSML｜tool_calls> <｜DSML｜invoke name="' + tool.name + '"> '
            '<｜DSML｜parameter name="arguments">{"code": "600519"}</｜DSML｜parameter> '
            "</｜DSML｜invoke> </｜DSML｜tool_calls>"
        )
        executor = _ScriptedExecutor([
            LLMTurn(content=leaked, reasoning_content="", tool_calls=(), finish_reason="stop"),
            LLMTurn(content="结论：已取得 600519 数据。", reasoning_content="", tool_calls=(), finish_reason="stop"),
        ])
        result = await executor.run(
            _profile((tool.name,)),
            "问题",
            None,
            llm_client=object(),
            model="test-model",
            execution_context=AgentExecutionContext(settings=Settings()),
        )
        # 外壳被拆掉后真的执行了，而不是把标记文本当成回答。
        assert executed == ["600519"]
        assert result.analysis == "结论：已取得 600519 数据。"
        assert "<｜DSML｜" not in result.analysis

    async def test_unexecutable_markup_is_stripped_from_the_answer(self, echo_tool):
        executor = _ScriptedExecutor([
            LLMTurn(content=LEAKED_DSML, reasoning_content="", tool_calls=(), finish_reason="stop"),
        ])
        # 该 Agent 没有任何工具：标记无法执行，但绝不允许当成结论给用户。
        result = await executor.run(
            _profile(()),
            "问题",
            None,
            llm_client=object(),
            model="test-model",
            execution_context=AgentExecutionContext(settings=Settings()),
        )
        assert "<｜DSML｜" not in result.analysis
        assert result.analysis == (
            "现在让我获取九安医疗的财务数据，以及查看美的集团和电投能源的机构一致预期数据。"
        )
        assert _TOOL_MARKUP_WARNING in result.warnings

    async def test_markup_only_answer_is_not_reported_as_output(self, echo_tool):
        executor = _ScriptedExecutor([
            LLMTurn(content=LEAKED_DSML.split("。")[-1], reasoning_content="", tool_calls=(), finish_reason="stop"),
        ])
        result = await executor.run(
            _profile(()),
            "问题",
            None,
            llm_client=object(),
            model="test-model",
            execution_context=AgentExecutionContext(settings=Settings()),
        )
        # 擦干净之后一个字都不剩：按「空回答」失败，而不是把标记当结论。
        assert result.analysis == ""
        assert result.status == "failed"


class TestContextBudgetStopsOfferingTools:
    """上下文预算耗尽后仍把工具摆给模型，会烧光 max_rounds 且拿不到任何输出。"""

    async def test_tools_are_withdrawn_and_the_agent_converges(self, echo_tool, monkeypatch):
        tool, executed = echo_tool
        settings = Settings()
        context = AgentExecutionContext(settings=settings)
        state = _ExecutionState(
            started_at=time.monotonic(),
            messages=[],
            effective_tool_names=[tool.name],
            tool_definitions=registry.get_tool_definitions_for([tool.name]),
            tool_cache=context.tool_cache,
            max_tool_context_characters=settings.chat_max_tool_context_characters,
        )
        # 预算已耗尽：此后再执行工具也只会被 _classify_tool_calls 整批拒绝。
        state.tool_context_characters = state.max_tool_context_characters
        executor = _ScriptedExecutor([
            LLMTurn(content="结论：基于已取得证据，缺口已记录。", reasoning_content="", tool_calls=(), finish_reason="stop"),
        ])
        monkeypatch.setattr(executor, "_build_execution_state", lambda *args, **kwargs: state)

        result = await executor.run(
            _profile((tool.name,)),
            "问题",
            None,
            llm_client=object(),
            model="test-model",
            execution_context=context,
        )

        assert executor.seen_tool_definitions == [()]  # 模型看不到工具
        assert executed == []  # 也没有白跑一次注定被拒的调用
        assert result.analysis == "结论：基于已取得证据，缺口已记录。"
        assert result.status == "partial"
        assert _TOOL_CONTEXT_WARNING in result.warnings


class TestStreamingMarkupFilterIsWired:
    """最终轮是边生成边推送的：标记必须在推给用户之前拦掉，事后无法撤回。"""

    async def test_streamed_deltas_never_contain_markup(self, monkeypatch):
        import app.agentic.agents.executor as executor_module

        async def fake_stream(_client, **_kwargs):
            for index in range(0, len(LEAKED_DSML), 9):
                yield {"choices": [{"delta": {"content": LEAKED_DSML[index:index + 9]}, "finish_reason": None}]}
            yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}

        monkeypatch.setattr(executor_module, "stream_chat_completion", fake_stream)
        emitted: list[str] = []

        async def emit(event) -> None:
            if event.type == "text":
                emitted.append(event.content)

        turn = await AgentExecutor()._complete_turn(
            object(),
            model="test-model",
            messages=[],
            tool_definitions=[],
            tool_choice="none",
            temperature=0.1,
            stream_response=True,
            emit=emit,
        )

        streamed = "".join(emitted)
        assert "DSML" not in streamed
        assert "<" not in streamed
        # 流里只可能残留标记被挖掉后剩下的空白，可读正文必须完整保留。
        assert streamed.strip() == (
            "现在让我获取九安医疗的财务数据，以及查看美的集团和电投能源的机构一致预期数据。"
        )
        assert turn.finish_reason == "stop"


class TestFailureReasonPrefersWarnings:
    """预算拒绝只写 warnings，不写 errors：失败原因必须仍然可操作。"""

    def test_warnings_are_used_when_no_error_text_exists(self):
        results = {
            "fundamental": AgentExecutionResult(
                agent_name="fundamental",
                display_name="基本面分析",
                analysis="",
                status="failed",
                tool_results=[ToolExecutionSummary(name="web_search", is_error=False, skipped=True)],
                warnings=[_TOOL_CONTEXT_WARNING],
            )
        }
        assert _summarize_failure_reasons(results) == _TOOL_CONTEXT_WARNING

    def test_generic_fallback_kept_when_nothing_is_recorded(self):
        results = {
            "fundamental": AgentExecutionResult(
                agent_name="fundamental", display_name="基本面分析", analysis="", status="failed"
            )
        }
        assert _summarize_failure_reasons(results) == "当前分析未生成有效结果，请稍后重试"


