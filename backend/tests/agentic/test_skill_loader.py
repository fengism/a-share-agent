"""SKILL.md loader: schema validation and built-in definition coverage."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.agentic_integration.skills.loader import SkillDefinitionError, load_builtin_skills


def _write_skill(
    root: Path,
    directory: str,
    *,
    body: str = "## Rules\n\n- use the tool\n",
    omit: tuple[str, ...] = (),
    **overrides,
) -> Path:
    data = {
        "name": directory,
        "description": "test skill",
        "triggers": ["test trigger"],
        "activation_keywords": ["test"],
        "tools": ["fake_tool"],
        "priority": 10,
    }
    data.update(overrides)
    for key in omit:
        data.pop(key, None)
    path = root / directory / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return path


def test_loads_valid_skill(tmp_path: Path):
    _write_skill(
        tmp_path,
        "valid_skill",
        triggers=["触发一", "触发二"],
        activation_keywords=["关键词"],
        tools=["tool_a", "tool_b"],
        priority=7,
        exclusions=["避免一"],
        examples=["示例一"],
        body="## Rules\n\n- 规则一\n- 规则二\n",
    )

    skills = load_builtin_skills(tmp_path)

    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "valid_skill"
    assert skill.triggers == ("触发一", "触发二")
    assert skill.activation_keywords == ("关键词",)
    assert skill.tool_names == ("tool_a", "tool_b")
    assert skill.rules == ("规则一", "规则二")
    assert skill.priority == 7
    assert skill.exclusions == ("避免一",)
    assert skill.examples == ("示例一",)


def test_priority_defaults_to_100(tmp_path: Path):
    _write_skill(tmp_path, "default_priority", omit=("priority",))

    assert load_builtin_skills(tmp_path)[0].priority == 100


def test_optional_lists_default_to_empty(tmp_path: Path):
    _write_skill(tmp_path, "optional_lists")

    skill = load_builtin_skills(tmp_path)[0]

    assert skill.exclusions == ()
    assert skill.examples == ()


def test_multiline_rule_is_joined(tmp_path: Path):
    _write_skill(tmp_path, "multiline", body="## Rules\n\n- first line\n  continuation\n")

    assert load_builtin_skills(tmp_path)[0].rules == ("first line continuation",)


def test_missing_frontmatter_fails(tmp_path: Path):
    path = tmp_path / "no_front" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("## Rules\n\n- rule\n", encoding="utf-8")

    with pytest.raises(SkillDefinitionError, match="frontmatter"):
        load_builtin_skills(tmp_path)


def test_invalid_yaml_fails(tmp_path: Path):
    path = tmp_path / "bad_yaml" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: [\n---\n\n## Rules\n\n- rule\n", encoding="utf-8")

    with pytest.raises(SkillDefinitionError, match="YAML"):
        load_builtin_skills(tmp_path)


def test_missing_required_field_fails(tmp_path: Path):
    _write_skill(tmp_path, "missing_tools", omit=("tools",))

    with pytest.raises(SkillDefinitionError, match="tools"):
        load_builtin_skills(tmp_path)


def test_unknown_field_fails(tmp_path: Path):
    _write_skill(tmp_path, "unknown_field", unexpected="value")

    with pytest.raises(SkillDefinitionError, match="未知字段"):
        load_builtin_skills(tmp_path)


def test_wrong_field_type_fails(tmp_path: Path):
    _write_skill(tmp_path, "wrong_type", triggers="not-a-list")

    with pytest.raises(SkillDefinitionError, match="字符串列表"):
        load_builtin_skills(tmp_path)


def test_directory_name_must_match_skill_name(tmp_path: Path):
    _write_skill(tmp_path, "directory_name", name="other_name")

    with pytest.raises(SkillDefinitionError, match="目录名"):
        load_builtin_skills(tmp_path)


def test_missing_rules_heading_fails(tmp_path: Path):
    _write_skill(tmp_path, "missing_rules", body="## Examples\n\n- example\n")

    with pytest.raises(SkillDefinitionError, match="Rules"):
        load_builtin_skills(tmp_path)


def test_empty_rules_fails(tmp_path: Path):
    _write_skill(tmp_path, "empty_rules", body="## Rules\n\n")

    with pytest.raises(SkillDefinitionError, match="至少需要一条"):
        load_builtin_skills(tmp_path)


def test_extra_heading_fails(tmp_path: Path):
    _write_skill(
        tmp_path,
        "extra_heading",
        body="## Rules\n\n- rule\n\n## Examples\n\n- example\n",
    )

    with pytest.raises(SkillDefinitionError, match="只能包含一个"):
        load_builtin_skills(tmp_path)


def test_default_definitions_load():
    skills = load_builtin_skills()

    expected = {
        "financial_calculations",
        "industry_research",
        "information_query",
        "market_data",
        "python_code_interpreter",
        "quant_strategy_authoring",
        "stock_analysis",
        "stock_screening",
        "twitter_account",
        "url_content",
    }
    assert {skill.name for skill in skills} == expected
    assert len({skill.name for skill in skills}) == len(skills)
    assert skills == sorted(skills, key=lambda skill: (skill.priority, skill.name))
    for skill in skills:
        assert skill.tool_names
        assert skill.rules
        assert skill.render_catalog(1)
        assert skill.render_instructions(1)


def test_core_tools_default_to_all_tools(tmp_path: Path):
    _write_skill(tmp_path, "no_core", tools=["tool_a", "tool_b"])

    skill = load_builtin_skills(tmp_path)[0]

    assert skill.core_tool_names == ()
    assert skill.initial_tool_names == ("tool_a", "tool_b")


def test_loads_core_tools(tmp_path: Path):
    _write_skill(
        tmp_path,
        "with_core",
        tools=["tool_a", "tool_b"],
        core_tools=["tool_a"],
    )

    skill = load_builtin_skills(tmp_path)[0]

    assert skill.core_tool_names == ("tool_a",)
    assert skill.initial_tool_names == ("tool_a",)


def test_rejects_core_tool_outside_tools(tmp_path: Path):
    _write_skill(
        tmp_path,
        "bad_core",
        tools=["tool_a"],
        core_tools=["tool_b"],
    )

    with pytest.raises(SkillDefinitionError):
        load_builtin_skills(tmp_path)
