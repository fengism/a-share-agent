from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.agents.executor import _llm_request_timeout
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.reviewer import PlanReview
from app.agentic.runtime.context import AgentExecutionContext
from app.modules.chat.orchestrator import (
    Orchestrator,
    _format_fallback_synthesis,
)


def test_execution_context_remaining_time():
    ctx_no_deadline = AgentExecutionContext(settings=SimpleNamespace())
    assert ctx_no_deadline.remaining_time() == float("inf")
    assert not ctx_no_deadline.deadline_exceeded()

    # Context with future deadline
    ctx_future = AgentExecutionContext(settings=SimpleNamespace(), deadline=100.0)
    with patch("time.monotonic", return_value=80.0):
        assert ctx_future.remaining_time() == 20.0
        assert not ctx_future.deadline_exceeded()

    # Context with expired deadline
    ctx_past = AgentExecutionContext(settings=SimpleNamespace(), deadline=100.0)
    with patch("time.monotonic", return_value=105.0):
        assert ctx_past.remaining_time() == 0.0
        assert ctx_past.deadline_exceeded()


def test_llm_request_timeout_bounded_by_chat_turn_timeout():
    settings = SimpleNamespace(
        chat_turn_timeout_seconds=90.0,
        llm_generation_timeout_seconds=1200.0,
    )
    # With plenty of deadline remaining, budget is capped at chat_turn_timeout_seconds (90s)
    ctx = AgentExecutionContext(settings=settings, deadline=1000.0)
    with patch("time.monotonic", return_value=100.0):
        timeout = _llm_request_timeout(ctx, settings)
        assert timeout == 90.0

    # With only 30s deadline remaining, timeout shrinks to remaining budget (30s)
    with patch("time.monotonic", return_value=970.0):
        timeout = _llm_request_timeout(ctx, settings)
        assert timeout == 30.0

    # Without deadline, it returns min(turn_cap, gen_budget)
    ctx_none = AgentExecutionContext(settings=settings, deadline=None)
    assert _llm_request_timeout(ctx_none, settings) == 90.0


def test_format_fallback_synthesis():
    results = {
        "technical": AgentExecutionResult(
            agent_name="technical",
            display_name="技术面分析",
            analysis="MACD金叉，短期多头排列。",
            status="completed",
        ),
        "fundamental": AgentExecutionResult(
            agent_name="fundamental",
            display_name="基本面分析",
            analysis="营收同比增长25%，毛利率稳定。",
            status="completed",
        ),
        "news": AgentExecutionResult(
            agent_name="news",
            display_name="消息面分析",
            analysis="",
            status="failed",
        ),
    }

    # Timed out mode
    text = _format_fallback_synthesis(results, timed_out=True)
    assert "触发安全时限" in text
    assert "### 技术面分析" in text
    assert "MACD金叉" in text
    assert "### 基本面分析" in text
    assert "营收同比增长25%" in text
    assert "### 消息面分析" not in text  # failed ones skipped

    # Budget insufficient mode
    text_short = _format_fallback_synthesis(results, timed_out=False)
    assert "不足以生成综合总结" in text_short
    assert "### 技术面分析" in text_short


@pytest.mark.asyncio
async def test_run_plan_with_review_skips_retry_when_time_is_short():
    settings = SimpleNamespace(chat_turn_timeout_seconds=120.0)
    # Remaining time is only 20 seconds (< 30.0 min_retry_seconds)
    ctx = AgentExecutionContext(settings=settings, deadline=100.0)
    with patch("time.monotonic", return_value=80.0):
        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.execution_context = ctx
        orchestrator.sub_agents = {}
        async def _dummy_stream(*args, **kwargs):
            if False:
                yield None

        orchestrator._run_sub_agents_streaming = MagicMock(side_effect=_dummy_stream)

        plan = ExecutionPlan(tasks=(AgentTask(task_id="t1", agent_name="technical", display_name="技术面", objective="技术指标分析", allowed_tools=()),))
        results = {"technical": AgentExecutionResult(agent_name="technical", display_name="技术面", analysis="", status="failed", retryable=True)}

        with patch("app.modules.chat.orchestrator.review_execution_plan") as mock_review:
            mock_review.return_value = PlanReview(issues=(), retry_task_ids=("t1",))
            events = []
            async for event in orchestrator._run_plan_with_review(
                plan, "msg", None, None, "m", results
            ):
                events.append(event)

            # Did not call retry streaming
            assert orchestrator._run_sub_agents_streaming.call_count == 1  # initial run only
            status_events = [e for e in events if e.type == "status" and "不再重跑任务" in e.content]
            assert len(status_events) == 1
