"""Dependency analyses are prepended to task messages and must stay bounded."""

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.orchestration.contracts import AgentTask
from app.agentic.orchestration.executor import _build_task_message, _render_dependency_context


def _result(agent_name: str, display_name: str, analysis: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=agent_name,
        display_name=display_name,
        analysis=analysis,
    )


def _task() -> AgentTask:
    return AgentTask(
        task_id="risk",
        agent_name="risk",
        display_name="风险",
        objective="评估下行风险",
        allowed_tools=(),
        dependencies=("fundamental", "technical"),
    )


def test_dependency_context_is_bounded_and_fairly_shared():
    rendered = _render_dependency_context(
        [
            _result("fundamental", "基本面", "A" * 20_000),
            _result("technical", "技术面", "B" * 20_000),
        ],
        max_characters=1_000,
    )

    assert len(rendered) <= 1_000
    assert "…（前置分析已按上下文预算截断）" in rendered
    # Both dependencies keep a roughly equal share instead of the first one
    # consuming the whole budget.
    assert rendered.count("A") > 100
    assert rendered.count("B") > 100


def test_dependency_context_is_unchanged_when_under_budget():
    rendered = _render_dependency_context(
        [
            _result("fundamental", "基本面", "基本面结论"),
            _result("technical", "技术面", "技术面结论"),
        ],
        max_characters=10_000,
    )

    assert "基本面结论" in rendered
    assert "技术面结论" in rendered
    assert "截断" not in rendered


def test_build_task_message_passes_the_budget_to_dependencies():
    message = _build_task_message(
        _task(),
        "请评估风险",
        {
            "fundamental": _result("fundamental", "基本面", "A" * 20_000),
            "technical": _result("technical", "技术面", "B" * 20_000),
        },
        max_dependency_characters=1_000,
    )

    assert message.startswith("请评估风险")
    assert "## 已完成的前置分析" in message
    assert "…（前置分析已按上下文预算截断）" in message
    assert "## 当前任务指示与要求\n评估下行风险" in message
