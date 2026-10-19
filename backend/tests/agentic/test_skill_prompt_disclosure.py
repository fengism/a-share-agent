"""Phase 2a: compact Skill catalog + top-N detailed instructions."""

from types import SimpleNamespace

from app.agentic.catalog import CapabilityCatalog
from app.agentic.skills.contracts import Skill
from app.agentic.tools.contracts import Tool
from app.modules.chat import general_agent


async def _executor():
    return {}


async def _load_skill_executor(name: str):
    return {"name": name}


def _skill(name: str, priority: int, rule: str) -> Skill:
    return Skill(
        name=name,
        description=f"{name} desc",
        triggers=(f"{name} trigger",),
        activation_keywords=(name,),
        tool_names=("fake_tool",),
        rules=(rule,),
        priority=priority,
        examples=(f"{name} example",),
    )


def _catalog() -> CapabilityCatalog:
    catalog = CapabilityCatalog()
    catalog.register_tool(Tool(
        name="fake_tool",
        description="fake",
        parameters={"type": "object", "properties": {}},
        executor=_executor,
    ))
    catalog.register_tool(Tool(
        name="load_skill",
        description="load a skill",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        executor=_load_skill_executor,
    ))
    catalog.register_skill(_skill("skill_a", 10, "rule-a"))
    catalog.register_skill(_skill("skill_b", 20, "rule-b"))
    return catalog


def test_render_prompt_is_catalog_plus_instructions():
    skill = _skill("skill_a", 10, "rule-a")

    assert skill.render_prompt(1) == "\n".join([
        skill.render_catalog(1),
        skill.render_instructions(1),
    ])


def test_catalog_excludes_rules_and_examples():
    catalog = _catalog()

    prompt = catalog.get_skill_catalog_prompt(["skill_a", "skill_b"])

    assert "skill_a" in prompt
    assert "skill_b" in prompt
    assert "skill_a desc" in prompt
    assert "skill_b desc" in prompt
    assert "rule-a" not in prompt
    assert "skill_a example" not in prompt


def test_instructions_are_limited_to_top_n():
    catalog = _catalog()

    prompt = catalog.get_skill_instructions(["skill_a", "skill_b"], limit=1)

    assert "## Skill 详细规则" in prompt
    assert "rule-a" in prompt
    assert "rule-b" not in prompt


def test_zero_limit_returns_no_instructions():
    catalog = _catalog()

    assert catalog.get_skill_instructions(["skill_a", "skill_b"], limit=0) == ""


def test_full_prompt_still_contains_all_rules():
    catalog = _catalog()

    prompt = catalog.get_skill_prompt(["skill_a", "skill_b"])

    assert "rule-a" in prompt
    assert "rule-b" in prompt


def test_general_agent_uses_catalog_plus_top_n(monkeypatch):
    catalog = _catalog()
    monkeypatch.setattr(general_agent, "registry", catalog)
    context = SimpleNamespace(settings=SimpleNamespace(chat_skill_instruction_top_n=1))

    prompt = general_agent._build_skill_prompt(["skill_a", "skill_b"], context)

    assert "skill_a" in prompt
    assert "skill_b" in prompt
    assert "skill_a desc" in prompt
    assert "skill_b desc" in prompt
    assert "rule-a" in prompt
    assert "rule-b" not in prompt


def test_zero_top_n_uses_catalog_only_and_hints_load_skill(monkeypatch):
    catalog = _catalog()
    monkeypatch.setattr(general_agent, "registry", catalog)
    context = SimpleNamespace(settings=SimpleNamespace(chat_skill_instruction_top_n=0))

    prompt = general_agent._build_skill_prompt(["skill_a", "skill_b"], context)

    assert "需要详细规则或更多工具时调用 load_skill(name)" in prompt
    assert "skill_a desc" in prompt
    assert "skill_b desc" in prompt
    assert "rule-a" not in prompt
    assert "rule-b" not in prompt


def test_negative_top_n_falls_back_to_full_prompt(monkeypatch):
    catalog = _catalog()
    monkeypatch.setattr(general_agent, "registry", catalog)
    context = SimpleNamespace(settings=SimpleNamespace(chat_skill_instruction_top_n=-1))

    prompt = general_agent._build_skill_prompt(["skill_a", "skill_b"], context)

    assert "rule-a" in prompt
    assert "rule-b" in prompt


def test_prompt_metrics_for_catalog_mode(monkeypatch):
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(general_agent, "metrics", fresh)
    catalog = _catalog()
    monkeypatch.setattr(general_agent, "registry", catalog)
    context = SimpleNamespace(settings=SimpleNamespace(chat_skill_instruction_top_n=0))

    general_agent._build_skill_prompt(["skill_a", "skill_b"], context)

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_catalog_injected"] == 1
    assert events["skill_prompt_mode_catalog"] == 1
    assert "skill_instructions_injected" not in events


def test_prompt_metrics_for_top_n_mode(monkeypatch):
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(general_agent, "metrics", fresh)
    catalog = _catalog()
    monkeypatch.setattr(general_agent, "registry", catalog)
    context = SimpleNamespace(settings=SimpleNamespace(chat_skill_instruction_top_n=1))

    general_agent._build_skill_prompt(["skill_a", "skill_b"], context)

    events = fresh.snapshot()["agentic"]["events"]
    assert events["skill_prompt_mode_top_n"] == 1
    assert events["skill_instructions_injected"] == 1


def test_real_catalog_exposes_every_skill_name():
    from app.agentic.catalog import registry
    from app.agentic_integration.bootstrap import register_all_capabilities

    register_all_capabilities()
    catalog = registry.get_skill_catalog_prompt()

    for skill in registry.list_skills():
        assert f"**{skill.name}**" in catalog


def test_catalog_marks_active_skills_as_recommended():
    catalog = _catalog()

    prompt = catalog.get_skill_catalog_prompt(
        ["skill_a", "skill_b"],
        active_skill_names=("skill_a",),
    )

    assert "**[推荐] skill_a**" in prompt
    assert "**[推荐] skill_b**" not in prompt
