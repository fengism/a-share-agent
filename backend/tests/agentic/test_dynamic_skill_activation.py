"""Phase 2c/P2: model-driven Skill activation and dynamic tool expansion."""

from app.agentic.events import AgentEvent
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic_integration.bootstrap import register_all_capabilities
from app.configuration import get_settings
from app.modules.chat import general_agent
from app.modules.chat.capability_plan import build_chat_capability_plan


def test_plan_exposes_enabled_tool_names():
    register_all_capabilities()

    plan = build_chat_capability_plan("分析茅台估值")

    assert "stock_analysis" in plan.enabled_skill_names
    assert "stock_analysis" in plan.active_skill_names
    assert set(plan.tool_names) <= set(plan.enabled_tool_names)
    assert "get_stock_info" in plan.enabled_tool_names


async def _capture_general_agent(monkeypatch) -> dict:
    captured: dict = {}

    async def fake_stream_agent(profile, message, history, **kwargs):
        captured["profile"] = profile
        captured["kwargs"] = kwargs
        yield AgentEvent(type="done", status="completed")

    monkeypatch.setattr(general_agent, "stream_agent", fake_stream_agent)
    return captured


async def test_general_agent_exposes_load_skill_for_enabled_skills(monkeypatch):
    register_all_capabilities()
    captured = await _capture_general_agent(monkeypatch)
    settings = get_settings().model_copy(update={
        "chat_skill_dynamic_activation_enabled": True,
        "chat_skill_instruction_top_n": 0,
    })
    context = AgentExecutionContext(settings=settings)

    async for _ in general_agent.stream_general_agent(
        "你好",
        tool_names=(),
        skill_names=(),
        enabled_skill_names=("stock_analysis",),
        enabled_tool_names=("get_stock_info",),
        execution_context=context,
    ):
        pass

    assert "load_skill" in captured["profile"].tool_names
    assert "load_skill" in captured["kwargs"]["allowed_tool_names"]
    assert "stock_analysis" in captured["kwargs"]["tool_selection_prompt"]
    assert context.allowed_skill_names == ("stock_analysis",)
    assert context.enabled_tool_names == ("get_stock_info",)
    assert context.active_skill_names == ()


async def test_dynamic_activation_disabled_falls_back_to_active_only(monkeypatch):
    register_all_capabilities()
    captured = await _capture_general_agent(monkeypatch)
    settings = get_settings().model_copy(update={
        "chat_skill_dynamic_activation_enabled": False,
        "chat_skill_instruction_top_n": 0,
    })
    context = AgentExecutionContext(settings=settings)

    async for _ in general_agent.stream_general_agent(
        "你好",
        tool_names=(),
        skill_names=(),
        enabled_skill_names=("stock_analysis",),
        enabled_tool_names=("get_stock_info",),
        execution_context=context,
    ):
        pass

    assert "load_skill" not in captured["profile"].tool_names
    assert captured["kwargs"]["tool_selection_prompt"] == ""
    assert context.allowed_skill_names == ()
    assert context.enabled_tool_names == ()
    assert context.active_skill_names == ()


def test_agentic_event_names_are_bounded():
    """动态事件前缀不能被无限撑大（工具名来自模型输出）。"""
    from app.core.metrics import _MAX_AGENTIC_EVENT_SERIES, MetricsRegistry

    fresh = MetricsRegistry()
    for index in range(_MAX_AGENTIC_EVENT_SERIES + 50):
        fresh.record_agentic_event(f"bogus_prefix_{index}")

    events = fresh.snapshot()["agentic"]["events"]
    # The overflow bucket itself is one extra series on top of the capped set.
    assert len(events) == _MAX_AGENTIC_EVENT_SERIES + 1
    assert events["agentic_event_series_overflow"] == 50
