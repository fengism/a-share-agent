"""Load built-in Skills from ``SKILL.md`` definitions.

Phase 1 keeps the existing ``Skill`` dataclass as the runtime contract. The
frontmatter carries routing metadata; the ``## Rules`` body carries the rules
that used to live in Python packs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.agentic.skills.contracts import Skill

DEFAULT_DEFINITIONS_DIR = Path(__file__).resolve().parent / "definitions"

_ALLOWED_KEYS = frozenset({
    "name",
    "description",
    "triggers",
    "activation_keywords",
    "tools",
    "core_tools",
    "priority",
    "exclusions",
    "examples",
})
_REQUIRED_KEYS = frozenset({
    "name",
    "description",
    "triggers",
    "activation_keywords",
    "tools",
})
_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<front>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(?P<body>.*)\Z",
    re.DOTALL,
)
_RULES_HEADING = re.compile(r"^##[ \t]+Rules[ \t]*$", re.MULTILINE)
_ANY_H2 = re.compile(r"^##[ \t]+.+$", re.MULTILINE)
_CACHE: dict[Path, tuple[Skill, ...]] = {}


class SkillDefinitionError(ValueError):
    """A ``SKILL.md`` file is missing required metadata or has an invalid shape."""


def _string_list(
    data: dict[str, Any],
    key: str,
    *,
    path: Path,
    required: bool,
) -> tuple[str, ...]:
    value = data.get(key)
    if value is None:
        if required:
            raise SkillDefinitionError(f"{path}: 缺少必填字段 {key!r}")
        return ()
    if not isinstance(value, list):
        raise SkillDefinitionError(f"{path}: 字段 {key!r} 必须是字符串列表")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SkillDefinitionError(
                f"{path}: 字段 {key!r}[{index}] 必须是非空字符串"
            )
        result.append(item)
    if required and not result:
        raise SkillDefinitionError(f"{path}: 字段 {key!r} 不能为空列表")
    return tuple(result)


def _priority(data: dict[str, Any], path: Path) -> int:
    value = data.get("priority", 100)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SkillDefinitionError(f"{path}: 字段 'priority' 必须是非负整数")
    return value


def _extract_rules(body: str, path: Path) -> tuple[str, ...]:
    headings = _ANY_H2.findall(body)
    if len(headings) != 1 or not _RULES_HEADING.search(body):
        raise SkillDefinitionError(
            f"{path}: 正文必须且只能包含一个 '## Rules' 二级标题，实际为 {headings!r}"
        )

    match = _RULES_HEADING.search(body)
    assert match is not None
    section = body[match.end():]
    next_heading = re.search(r"^##[ \t]+", section, re.MULTILINE)
    if next_heading is not None:
        section = section[:next_heading.start()]

    rules: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            rules.append(" ".join(current).strip())
            current.clear()

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith("- "):
            flush()
            current.append(line[2:].strip())
        elif current:
            current.append(line)
        else:
            raise SkillDefinitionError(
                f"{path}: '## Rules' 下的内容必须是 '- ' 开头的列表项"
            )
    flush()

    if not rules or any(not rule for rule in rules):
        raise SkillDefinitionError(f"{path}: '## Rules' 至少需要一条非空规则")
    return tuple(rules)


def _load_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8-sig")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise SkillDefinitionError(f"{path}: 缺少 '---' 包裹的 YAML frontmatter")

    try:
        data = yaml.safe_load(match.group("front"))
    except yaml.YAMLError as error:
        raise SkillDefinitionError(f"{path}: YAML frontmatter 解析失败：{error}") from error
    if not isinstance(data, dict):
        raise SkillDefinitionError(f"{path}: YAML frontmatter 必须是对象")

    unknown = sorted(set(data) - _ALLOWED_KEYS)
    if unknown:
        raise SkillDefinitionError(f"{path}: 未知字段 {unknown}")
    missing = sorted(_REQUIRED_KEYS - set(data))
    if missing:
        raise SkillDefinitionError(f"{path}: 缺少必填字段 {missing}")

    name = data["name"]
    description = data["description"]
    if not isinstance(name, str) or not name.strip():
        raise SkillDefinitionError(f"{path}: 字段 'name' 必须是非空字符串")
    if not isinstance(description, str) or not description.strip():
        raise SkillDefinitionError(f"{path}: 字段 'description' 必须是非空字符串")
    if path.parent.name != name:
        raise SkillDefinitionError(
            f"{path}: 目录名 {path.parent.name!r} 与 skill name {name!r} 不一致"
        )

    try:
        return Skill(
            name=name,
            description=description,
            triggers=_string_list(data, "triggers", path=path, required=True),
            activation_keywords=_string_list(
                data, "activation_keywords", path=path, required=True
            ),
            tool_names=_string_list(data, "tools", path=path, required=True),
            core_tool_names=_string_list(data, "core_tools", path=path, required=False),
            rules=_extract_rules(match.group("body"), path),
            priority=_priority(data, path),
            exclusions=_string_list(data, "exclusions", path=path, required=False),
            examples=_string_list(data, "examples", path=path, required=False),
        )
    except ValueError as error:
        raise SkillDefinitionError(f"{path}: Skill 校验失败：{error}") from error


def load_builtin_skills(definitions_dir: Path | None = None) -> list[Skill]:
    """Load all ``definitions/*/SKILL.md`` files, sorted by priority and name."""
    root = (definitions_dir or DEFAULT_DEFINITIONS_DIR).resolve()
    cached = _CACHE.get(root)
    if cached is not None:
        return list(cached)
    if not root.is_dir():
        raise SkillDefinitionError(f"{root}: Skill definitions 目录不存在")

    paths = sorted(root.glob("*/SKILL.md"))
    if not paths:
        raise SkillDefinitionError(f"{root}: 没有找到任何 SKILL.md")

    skills: list[Skill] = []
    seen: set[str] = set()
    for path in paths:
        skill = _load_skill(path)
        if skill.name in seen:
            raise SkillDefinitionError(f"{path}: Skill name {skill.name!r} 重复")
        seen.add(skill.name)
        skills.append(skill)

    skills.sort(key=lambda skill: (skill.priority, skill.name))
    _CACHE[root] = tuple(skills)
    return list(skills)


__all__ = ["DEFAULT_DEFINITIONS_DIR", "SkillDefinitionError", "load_builtin_skills"]
