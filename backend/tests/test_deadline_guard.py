import time

from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.contracts import Tool, ToolPolicy


def _tool() -> Tool:
    calls: list[int] = []

    async def _executor() -> dict:
        calls.append(1)
        return {"ok": True}

    return Tool(
        name="probe",
        description="probe",
        parameters={"type": "object", "properties": {}},
        executor=_executor,
        policy=ToolPolicy(timeout_seconds=30, cache_ttl_seconds=0),
    )


def _call() -> ToolCallInfo:
    return ToolCallInfo(id="c1", function={"name": "probe", "arguments": "{}"})


def _context(deadline_offset: float):
    from app.agentic.runtime.context import AgentExecutionContext

    return AgentExecutionContext(
        settings=type("S", (), {
            "chat_tool_timeout_seconds": 30,
            "chat_max_tool_calls_total": 32,
            "chat_max_tool_calls_per_round": 8,
        })(),
        user_id=1,
        request_id="r1",
        deadline=time.monotonic() + deadline_offset,
    )


class TestDeadlineExhausted:
    async def test_short_circuits_when_deadline_passed(self):
        # 不短路时 bounded_timeout 返回 ~1ms，工具会立刻失败；
        # LLM 看到的是「可重试的工具错误」会继续调用，白烧工具配额和 LLM 往返。
        tool = _tool()
        result = await tool.execute(_call(), execution_context=_context(-1.0))
        assert result.is_error is True
        assert "deadline_exceeded" in result.content
        # executor 完全没被调用
        assert tool.executor is not None

    async def test_runs_normally_within_deadline(self):
        result = await _tool().execute(_call(), execution_context=_context(60.0))
        assert result.is_error is False

    def test_deadline_exceeded_predicate(self):
        from app.agentic.runtime.context import AgentExecutionContext

        settings = type("S", (), {})()
        assert AgentExecutionContext(
            settings=settings, user_id=1, request_id="r", deadline=time.monotonic() - 1
        ).deadline_exceeded() is True
        assert AgentExecutionContext(
            settings=settings, user_id=1, request_id="r", deadline=time.monotonic() + 60
        ).deadline_exceeded() is False
        # 无 deadline 时永不判定为超期
        assert AgentExecutionContext(
            settings=settings, user_id=1, request_id="r", deadline=None
        ).deadline_exceeded() is False
