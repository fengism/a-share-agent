"""The on-demand load_skill tool and its instruction/evidence semantics."""

import json
from types import SimpleNamespace

from app.agentic.catalog import CapabilityCatalog
from app.agentic.protocol import ToolCallFunction, ToolCallInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.skills.contracts import Skill
from app.agentic.tools.contracts import Tool
from app.agentic_integration.skills import registration
from app.agentic_integration.skills.registration import register_skill_tools


async def _fake_executor():
    return {}


def _skill(name: str, rule: str) -> Skill:
    return Skill(
        name=name,
        description=f"{name} desc",
        triggers=(f"{name} trigger",),
        activation_keywords=(name,),
        tool_names=("fake_tool",),
        rules=(rule,),
        examples=(f"{name} example",),
    )


def _catalog() -> CapabilityCatalog:
    catalog = CapabilityCatalog()
    catalog.register_tool(Tool(
        name="fake_tool",
        description="fake",
        parameters={"type": "object", "properties": {}},
        executor=_fake_executor,
    ))
    catalog.register_skill(_skill("skill_a", "rule-a"))
    catalog.register_skill(_skill("skill_b", "rule-b"))
    register_skill_tools(catalog)
    return catalog


def _call(name: str) -> ToolCallInfo:
    return ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(
            name="load_skill",
            arguments=json.dumps({"name": name}),
        ),
    )


def _context(allowed: tuple[str, ...] | None) -> AgentExecutionContext:
    return AgentExecutionContext(
        settings=SimpleNamespace(chat_tool_timeout_seconds=10),
        allowed_skill_names=allowed,
    )


async def test_load_skill_returns_instructions_for_allowed_skill():
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None

    result = await tool.execute(_call("skill_a"), execution_context=_context(("skill_a",)))

    assert result.is_error is False
    payload = json.loads(result.content)
    data = payload["data"]
    assert data["kind"] == "skill_instructions"
    assert data["name"] == "skill_a"
    assert "rule-a" in data["instructions"]
    assert data["tools"] == ["fake_tool"]
    assert data["tools_available_next_turn"] is True
    assert "指令" in data["note"]


async def test_load_skill_rejects_skill_not_enabled_for_this_session():
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None

    result = await tool.execute(_call("skill_a"), execution_context=_context(("skill_b",)))

    assert result.is_error is True
    payload = json.loads(result.content)
    assert payload["error"]["code"] == "bad_request"


async def test_load_skill_rejects_unknown_skill():
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None

    result = await tool.execute(_call("missing"), execution_context=_context(None))

    assert result.is_error is True
    payload = json.loads(result.content)
    assert payload["error"]["code"] == "bad_request"


def test_load_skill_policy_is_not_data_evidence():
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None
    assert tool.policy.evidence is False
    assert tool.policy.budget == "skill"


async def test_load_skill_records_success_metrics(monkeypatch):
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(registration, "metrics", fresh)
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None

    await tool.execute(_call("skill_a"), execution_context=_context(("skill_a",)))

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_load_success"] == 1


async def test_load_skill_records_rejection_metrics(monkeypatch):
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(registration, "metrics", fresh)
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None

    await tool.execute(_call("skill_a"), execution_context=_context(("skill_b",)))

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_load_rejected"] == 1


async def test_load_skill_records_unknown_metrics(monkeypatch):
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(registration, "metrics", fresh)
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None

    await tool.execute(_call("missing"), execution_context=_context(None))

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_load_unknown"] == 1


async def test_load_skill_reports_unavailable_tools():
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None
    context = AgentExecutionContext(
        settings=SimpleNamespace(chat_tool_timeout_seconds=10),
        allowed_skill_names=("skill_a",),
        enabled_tool_names=("other_tool",),
    )

    result = await tool.execute(_call("skill_a"), execution_context=context)

    payload = json.loads(result.content)
    assert payload["data"]["unavailable_tools"] == ["fake_tool"]


async def test_load_skill_records_after_initial_metrics(monkeypatch):
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(registration, "metrics", fresh)
    catalog = _catalog()
    tool = catalog.get_tool("load_skill")
    assert tool is not None
    context = AgentExecutionContext(
        settings=SimpleNamespace(chat_tool_timeout_seconds=10),
        allowed_skill_names=("skill_a",),
        active_skill_names=("skill_a",),
    )

    await tool.execute(_call("skill_a"), execution_context=context)

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_load_after_initial:skill_a"] == 1
