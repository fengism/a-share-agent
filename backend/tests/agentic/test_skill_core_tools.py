"""Per-Skill core_tools: first-turn convergence with load_skill expansion."""

import pytest

from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.skills.contracts import Skill
from app.agentic.tools.contracts import Tool
from app.agentic_integration.bootstrap import register_all_capabilities
from app.modules.chat.capability_plan import build_chat_capability_plan


async def _executor():
    return {}


def _tool(name: str) -> Tool:
    return Tool(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}},
        executor=_executor,
    )


def _skill(**overrides) -> Skill:
    data = {
        "name": "sk",
        "description": "desc",
        "triggers": ("t",),
        "activation_keywords": ("sk",),
        "tool_names": ("tool_a", "tool_b"),
        "rules": ("r",),
    }
    data.update(overrides)
    return Skill(**data)


def test_skill_defaults_initial_tools_to_all():
    assert _skill().initial_tool_names == ("tool_a", "tool_b")


def test_skill_rejects_core_tools_outside_tools():
    with pytest.raises(ValueError):
        _skill(core_tool_names=("tool_c",))


def test_catalog_separates_initial_and_full_tools():
    catalog = CapabilityCatalog()
    for name in ("tool_a", "tool_b", "tool_c"):
        catalog.register_tool(_tool(name))
    catalog.register_skill(_skill(tool_names=("tool_a", "tool_b", "tool_c"), core_tool_names=("tool_a",)))

    assert catalog.get_initial_tool_names_for_skills(("sk",)) == ["tool_a"]
    assert catalog.get_tool_names_for_skills(("sk",)) == ["tool_a", "tool_b", "tool_c"]


def test_plan_uses_core_tools_for_initial_skills():
    register_all_capabilities()

    plan = build_chat_capability_plan("分析茅台估值", max_initial_active_skills=1)

    assert plan.initial_skill_names == ("stock_analysis",)
    assert plan.tool_names == tuple(
        registry.get_initial_tool_names_for_skills(plan.initial_skill_names)
    )
    assert set(plan.tool_names) < set(plan.active_tool_names)
    assert "get_stock_documents" not in plan.tool_names
    assert "get_stock_documents" in plan.enabled_tool_names


def test_plan_can_fall_back_to_full_initial_tools():
    register_all_capabilities()

    plan = build_chat_capability_plan(
        "分析茅台估值",
        max_initial_active_skills=1,
        core_tools_enabled=False,
    )

    assert plan.tool_names == tuple(
        registry.get_tool_names_for_skills(plan.initial_skill_names)
    )
    assert "get_stock_documents" in plan.tool_names


def test_expand_skill_tools_adds_non_core_tools(monkeypatch):
    from types import SimpleNamespace

    from app.agentic.agents import executor as executor_module
    from app.agentic.runtime.context import AgentExecutionContext
    from app.configuration import get_settings
    from app.core.metrics import MetricsRegistry

    register_all_capabilities()
    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    state = SimpleNamespace(effective_tool_names=[], tool_definitions=[])
    context = AgentExecutionContext(
        settings=get_settings(),
        enabled_tool_names=("get_stock_documents",),
    )

    executor_module.AgentExecutor()._expand_skill_tools(
        state,
        context,
        '{"data":{"kind":"skill_instructions","tools":["get_stock_documents"]}}',
    )

    assert state.effective_tool_names == ["get_stock_documents"]
    assert fresh.snapshot()["agentic"]["events"]["skill_tools_expanded"] == 1


def test_expand_skill_tools_records_core_miss_metrics(monkeypatch):
    from types import SimpleNamespace

    from app.agentic.agents import executor as executor_module
    from app.agentic.runtime.context import AgentExecutionContext
    from app.configuration import get_settings
    from app.core.metrics import MetricsRegistry

    register_all_capabilities()
    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)
    state = SimpleNamespace(effective_tool_names=[], tool_definitions=[])
    context = AgentExecutionContext(
        settings=get_settings(),
        enabled_tool_names=("get_stock_documents",),
    )

    executor_module.AgentExecutor()._expand_skill_tools(
        state,
        context,
        '{"data":{"kind":"skill_instructions","name":"stock_analysis",'
        '"tools":["get_stock_documents"]}}',
    )

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_tools_expanded"] == 1
    assert events["skill_initial_tools_expanded"] == 1
    assert events["skill_core_tool_missed:get_stock_documents"] == 1
