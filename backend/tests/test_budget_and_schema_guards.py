"""预算、schema 关键字与注册原子性的回归护栏。

1. 工具结果上下文预算只增不减，耗尽后工具照跑、额度照扣，而结果被整条挤掉——模型
   什么都看不到。修复前还会产出空串 tool message。
2. ``exclusiveMinimum`` / ``exclusiveMaximum`` / ``multipleOf`` / ``const`` 从未实现，
   且 ``validate_schema`` 不检查未知关键字：schema 声明了约束、模型以为是合法区间，
   值一路穿到 pydantic 才被拒，最终只得到一个不透明的 execution_failed。
3. 预算拒绝的 ``is_error=False`` 让 Reviewer 的两个判定都看不到它，零证据任务被当成
   usable 注入下游。
4. 注册用裸 bool 做门闩且中途失败不回滚，会永久毒化 registry。
"""
import asyncio
import json
import time

import pytest

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile, ToolExecutionSummary
from app.agentic.agents.executor import AgentExecutor, _ExecutionState
from app.agentic.catalog import registry
from app.agentic.events import _tool_result_summary
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.reviewer import is_usable_task_result, review_execution_plan
from app.agentic.protocol import ToolCallInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools import registration as tool_registration
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.agentic.tools.validation import (
    SUPPORTED_SCHEMA_KEYWORDS,
    ToolArgumentsError,
    validate_schema,
    validate_value,
)
from app.configuration.schema import Settings
from app.infrastructure.llm.capabilities import DEFAULT_LLM_CAPABILITIES

_EXECUTED: list[str] = []


@pytest.fixture
def counting_tool():
    name = "stub_budget_guard"

    async def executor() -> dict:
        _EXECUTED.append(name)
        return {"v": 1}

    tool = Tool(
        name=name,
        description="测试用",
        parameters={"type": "object", "properties": {}},
        executor=executor,
        policy=ToolPolicy(cache_ttl_seconds=0),
    )
    registry.register_tool(tool)
    _EXECUTED.clear()
    yield tool
    registry._tools.pop(name, None)


async def _run_tool_calls(tool, *, max_context: int, used: int) -> tuple[list, object]:
    profile = AgentProfile(
        name="budget_tester",
        display_name="预算测试",
        description="测试",
        system_prompt="prompt",
        tool_names=(tool.name,),
    )
    state = _ExecutionState(
        started_at=time.monotonic(),
        messages=[],
        effective_tool_names=list(profile.tool_names),
        tool_definitions=[],
        tool_cache=AgentExecutionContext(settings=Settings()).tool_cache,
        max_tool_context_characters=max_context,
    )
    state.tool_context_characters = used
    events: list = []

    async def emit(event) -> None:
        events.append(event)

    context = AgentExecutionContext(settings=Settings(chat_max_tool_calls_total=8))
    await AgentExecutor()._execute_tool_calls(
        profile,
        state,
        [ToolCallInfo(id="c1", function={"name": tool.name, "arguments": "{}"})],
        "",
        emit,
        context,
        0,
        DEFAULT_LLM_CAPABILITIES,
    )
    result_events = [event for event in events if event.type == "tool_result"]
    assert result_events
    return state.tool_results, result_events[0]


class TestContextBudgetExhaustionStopsToolCalls:
    async def test_tool_is_not_executed(self, counting_tool):
        summaries, _ = await _run_tool_calls(
            counting_tool, max_context=100, used=100
        )
        assert _EXECUTED == []
        assert len(summaries) == 1
        assert summaries[0].skipped is True
        assert summaries[0].is_error is False

    async def test_rejection_carries_an_explicit_code(self, counting_tool):
        _, event = await _run_tool_calls(counting_tool, max_context=100, used=100)
        payload = json.loads(event.tool_result.content)
        assert payload["error"]["code"] == "tool_context_budget_exhausted"
        assert "上下文预算已用尽" in payload["error"]["message"]

    async def test_message_content_is_never_empty(self, counting_tool):
        # 修复前预算耗尽会产出 content="" 的 tool message（协议风险 + 模型看不到任何东西）。
        profile = AgentProfile(
            name="budget_tester2",
            display_name="预算测试",
            description="测试",
            system_prompt="prompt",
            tool_names=(counting_tool.name,),
        )
        state = _ExecutionState(
            started_at=time.monotonic(),
            messages=[],
            effective_tool_names=list(profile.tool_names),
            tool_definitions=[],
            tool_cache=AgentExecutionContext(settings=Settings()).tool_cache,
            max_tool_context_characters=100,
        )
        state.tool_context_characters = 100

        async def emit(_event) -> None:
            return None

        await AgentExecutor()._execute_tool_calls(
            profile,
            state,
            [ToolCallInfo(id="c1", function={"name": counting_tool.name, "arguments": "{}"})],
            "",
            emit,
            AgentExecutionContext(settings=Settings(chat_max_tool_calls_total=8)),
            0,
            DEFAULT_LLM_CAPABILITIES,
        )
        tool_messages = [m for m in state.messages if m.get("role") == "tool"]
        assert tool_messages
        assert all(message["content"] for message in tool_messages)

    async def test_ui_shows_skipped_not_failure(self, counting_tool):
        _, event = await _run_tool_calls(counting_tool, max_context=100, used=100)
        summary = _tool_result_summary(event.tool_result)
        assert summary.status == "skipped"
        assert "未实际执行" in summary.summary

    async def test_budget_available_still_executes(self, counting_tool):
        summaries, _ = await _run_tool_calls(counting_tool, max_context=8000, used=10)
        assert _EXECUTED == [counting_tool.name]
        assert summaries[0].skipped is False
        assert summaries[0].has_evidence is True


class TestUnimplementedSchemaKeywords:
    def test_exclusive_minimum_is_enforced(self):
        with pytest.raises(ToolArgumentsError) as excinfo:
            validate_value(0, {"type": "number", "exclusiveMinimum": 0})
        assert excinfo.value.reason == "below_exclusive_minimum"
        validate_value(0.5, {"type": "number", "exclusiveMinimum": 0})

    def test_exclusive_maximum_is_enforced(self):
        with pytest.raises(ToolArgumentsError) as excinfo:
            validate_value(5, {"type": "number", "exclusiveMaximum": 5})
        assert excinfo.value.reason == "above_exclusive_maximum"
        validate_value(4.9, {"type": "number", "exclusiveMaximum": 5})

    def test_multiple_of_is_enforced(self):
        with pytest.raises(ToolArgumentsError) as excinfo:
            validate_value(7, {"type": "number", "multipleOf": 5})
        assert excinfo.value.reason == "not_multiple_of"
        validate_value(10, {"type": "number", "multipleOf": 5})

    def test_const_is_enforced(self):
        with pytest.raises(ToolArgumentsError) as excinfo:
            validate_value("b", {"const": "a"})
        assert excinfo.value.reason == "const_mismatch"
        validate_value("a", {"const": "a"})

    def test_real_tool_rejects_the_value_its_schema_forbids(self):
        # backtest_quant_strategy_draft 的 maximum_drawdown_pct 声明了
        # exclusiveMinimum: 0；修复前 0 会一路穿到 pydantic，模型只拿到
        # 一个不透明的 execution_failed（错误编号）。
        from app.agentic.tools.registration import register_all_tools

        register_all_tools()
        tool = registry.get_tool("backtest_quant_strategy_draft")
        result = asyncio.run(
            tool.execute(
                ToolCallInfo(
                    id="c1",
                    function={
                        "name": "backtest_quant_strategy_draft",
                        "arguments": json.dumps(
                            {
                                "draft_id": "d1",
                                "codes": ["600519"],
                                "start_date": "2026-01-01",
                                "end_date": "2026-06-30",
                                "maximum_drawdown_pct": 0,
                            }
                        ),
                    },
                )
            )
        )
        assert result.is_error is True
        payload = json.loads(result.content)
        assert payload["error"]["code"] == "invalid_arguments"
        assert payload["data"]["argument_error"]["reason"] == "below_exclusive_minimum"

    @pytest.mark.parametrize(
        "keyword", ["allOf", "anyOf", "oneOf", "not", "patternProperties", "if", "const_ok"]
    )
    def test_unknown_keywords_fail_registration(self, keyword):
        with pytest.raises(ValueError, match="未实现的关键字"):
            validate_schema({"type": "object", "properties": {"x": {keyword: []}}})

    def test_whitelist_covers_every_registered_tool(self):
        from app.agentic.tools.registration import register_all_tools

        register_all_tools()
        seen: set[str] = set()

        def walk(node) -> None:
            if isinstance(node, dict):
                seen.update(node)
                properties = node.get("properties")
                if isinstance(properties, dict):
                    for sub in properties.values():
                        walk(sub)
                    return
                for key, sub in node.items():
                    if key not in {"properties", "default", "enum", "description"}:
                        walk(sub)

        for tool in registry._tools.values():
            walk(tool.parameters)
        assert seen <= SUPPORTED_SCHEMA_KEYWORDS, sorted(seen - SUPPORTED_SCHEMA_KEYWORDS)


class TestSkippedCallsAreVisibleToTheReviewer:
    @staticmethod
    def _task() -> AgentTask:
        return AgentTask(
            task_id="t1",
            agent_name="alpha",
            display_name="甲",
            objective="分析甲",
            allowed_tools=("web_search",),
        )

    @staticmethod
    def _result(summaries: list[ToolExecutionSummary]) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_name="alpha",
            display_name="甲",
            analysis="已完成分析",
            status="completed",
            tools_called=[item.name for item in summaries],
            tool_results=summaries,
        )

    def test_all_skipped_is_not_usable(self):
        result = self._result([ToolExecutionSummary(name="web_search", is_error=False, skipped=True)])
        assert is_usable_task_result(self._task(), result) is False

    def test_all_failed_is_not_usable(self):
        result = self._result([ToolExecutionSummary(name="web_search", is_error=True)])
        assert is_usable_task_result(self._task(), result) is False

    def test_mixed_skip_and_success_is_usable(self):
        result = self._result(
            [
                ToolExecutionSummary(name="web_search", is_error=False, has_evidence=True, skipped=True),
                ToolExecutionSummary(name="web_fetch", is_error=False, has_evidence=True),
            ]
        )
        assert is_usable_task_result(self._task(), result) is True

    def test_reviewer_flags_all_skipped(self):
        task = self._task()
        plan = ExecutionPlan(tasks=(task,))
        result = self._result([ToolExecutionSummary(name="web_search", is_error=False, skipped=True)])
        review = review_execution_plan(plan, {"alpha": result})
        assert review.should_retry is True
        assert "跳过" in review.issues[0].reason


class TestRegistrationIsAtomicAndRetryable:
    def test_failed_registration_rolls_back_and_can_retry(self, monkeypatch):
        snapshot = dict(registry._tools)
        registry._tools.clear()
        monkeypatch.setattr(tool_registration, "_tools_registered", False)

        def broken() -> None:
            raise ValueError("schema 坏了")

        monkeypatch.setattr(tool_registration, "register_market_tools", broken)
        with pytest.raises(ValueError, match="schema 坏了"):
            tool_registration.register_all_tools()
        # 半套工具不能留在全局 registry 里，否则重跑会撞「已注册」而永久失败。
        assert registry._tools == {}

        # 修好之后必须能重新注册成功。
        monkeypatch.undo()
        monkeypatch.setattr(tool_registration, "_tools_registered", False)
        try:
            tool_registration.register_all_tools()
            assert "analyze_financials" in registry._tools
            assert "web_search" in registry._tools
        finally:
            registry._tools.clear()
            registry._tools.update(snapshot)
            monkeypatch.setattr(tool_registration, "_tools_registered", True)

    def test_concurrent_registration_registers_each_tool_once(self, monkeypatch):
        snapshot = dict(registry._tools)
        registry._tools.clear()
        monkeypatch.setattr(tool_registration, "_tools_registered", False)
        import threading

        errors: list[BaseException] = []

        def run() -> None:
            try:
                tool_registration.register_all_tools()
            except BaseException as error:  # noqa: BLE001 - 测试要看到并发下的失败
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        try:
            assert errors == []
            assert "analyze_financials" in registry._tools
        finally:
            registry._tools.clear()
            registry._tools.update(snapshot)
            monkeypatch.setattr(tool_registration, "_tools_registered", True)
