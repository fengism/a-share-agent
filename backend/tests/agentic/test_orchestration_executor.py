"""Execution-plan DAG: dependency context and blocked downstream tasks."""

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile, ToolExecutionSummary
from app.agentic.orchestration import executor as orchestration_executor
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan


def _profile(name: str, display_name: str) -> AgentProfile:
    return AgentProfile(
        name=name,
        display_name=display_name,
        description="test",
        system_prompt="system",
        tool_names=("fake_tool",),
    )


def _usable_result(profile: AgentProfile, analysis: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=profile.name,
        display_name=profile.display_name,
        analysis=analysis,
        status="completed",
        tools_called=["fake_tool"],
        tool_results=[ToolExecutionSummary(
            name="fake_tool",
            is_error=False,
            has_evidence=True,
            context_has_evidence=True,
        )],
    )


def _plan() -> ExecutionPlan:
    return ExecutionPlan(tasks=(
        AgentTask(
            task_id="fundamental",
            agent_name="fundamental",
            display_name="基本面",
            objective="分析基本面",
            allowed_tools=("fake_tool",),
        ),
        AgentTask(
            task_id="risk",
            agent_name="risk",
            display_name="风险",
            objective="评估风险",
            allowed_tools=("fake_tool",),
            dependencies=("fundamental",),
        ),
    ))


async def _collect(stream) -> list:
    return [event async for event in stream]


async def test_plan_passes_dependency_analysis_to_downstream_task(monkeypatch):
    agents = {
        "fundamental": _profile("fundamental", "基本面"),
        "risk": _profile("risk", "风险"),
    }
    messages: dict[str, str] = {}

    async def fake_run(profile, message, history, client, model, **kwargs):
        messages[profile.name] = message
        return _usable_result(profile, f"{profile.display_name}结论")

    monkeypatch.setattr(orchestration_executor.agent_executor, "run", fake_run)

    results: dict[str, AgentExecutionResult] = {}
    await _collect(orchestration_executor.stream_execution_plan(
        agents,
        _plan(),
        "请分析",
        None,
        None,
        "fake-model",
        results,
    ))

    assert set(results) == {"fundamental", "risk"}
    assert "基本面结论" in messages["risk"]
    assert results["risk"].status == "completed"


async def test_plan_blocks_downstream_when_dependency_is_unusable(monkeypatch):
    agents = {
        "fundamental": _profile("fundamental", "基本面"),
        "risk": _profile("risk", "风险"),
    }
    messages: dict[str, str] = {}

    async def fake_run(profile, message, history, client, model, **kwargs):
        messages[profile.name] = message
        if profile.name == "risk":
            raise AssertionError("blocked downstream task must not run")
        return AgentExecutionResult(
            agent_name=profile.name,
            display_name=profile.display_name,
            analysis="",
            status="failed",
            errors=["基本面失败"],
        )

    monkeypatch.setattr(orchestration_executor.agent_executor, "run", fake_run)

    results: dict[str, AgentExecutionResult] = {}
    await _collect(orchestration_executor.stream_execution_plan(
        agents,
        _plan(),
        "请分析",
        None,
        None,
        "fake-model",
        results,
    ))

    assert "risk" not in messages
    assert results["risk"].status == "failed"
    assert results["risk"].termination_reason == "dependency_unavailable"


def _skill_context(*, skill_instructions_enabled: bool = True):
    from types import SimpleNamespace

    from app.agentic.runtime.context import AgentExecutionContext

    return AgentExecutionContext(
        settings=SimpleNamespace(
            chat_agent_skill_instructions_enabled=skill_instructions_enabled,
            chat_max_tool_context_characters=60_000,
        )
    )


def _skill_profile() -> AgentProfile:
    return AgentProfile(
        name="fundamental",
        display_name="基本面",
        description="test",
        system_prompt="system",
        tool_names=("fake_tool",),
        skill_names=("stock_analysis",),
    )


def test_professional_skill_prompt_injects_declared_rules():
    from app.agentic_integration.bootstrap import register_all_capabilities

    register_all_capabilities()
    prompt = orchestration_executor._build_professional_skill_prompt(
        _skill_profile(),
        _skill_context(),
    )

    assert "## Skill 详细规则" in prompt
    assert "个股识别" in prompt


def test_professional_skill_prompt_respects_toggle():
    from app.agentic_integration.bootstrap import register_all_capabilities

    register_all_capabilities()
    prompt = orchestration_executor._build_professional_skill_prompt(
        _skill_profile(),
        _skill_context(skill_instructions_enabled=False),
    )

    assert prompt == ""


async def test_plan_forwards_professional_skill_prompt(monkeypatch):
    from app.agentic_integration.bootstrap import register_all_capabilities

    register_all_capabilities()
    profile = _skill_profile()
    plan = ExecutionPlan(tasks=(
        AgentTask(
            task_id="fundamental",
            agent_name="fundamental",
            display_name="基本面",
            objective="分析基本面",
            allowed_tools=("fake_tool",),
        ),
    ))
    captured: dict[str, str] = {}

    async def fake_run(profile, message, history, client, model, **kwargs):
        captured["prompt"] = kwargs.get("tool_selection_prompt", "")
        return _usable_result(profile, "结论")

    monkeypatch.setattr(orchestration_executor.agent_executor, "run", fake_run)

    results: dict[str, AgentExecutionResult] = {}
    await _collect(orchestration_executor.stream_execution_plan(
        {"fundamental": profile},
        plan,
        "请分析",
        None,
        None,
        "fake-model",
        results,
        execution_context=_skill_context(),
    ))

    assert "## Skill 详细规则" in captured["prompt"]
