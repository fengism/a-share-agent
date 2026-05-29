from __future__ import annotations

import json
import re

from app.models.chat import ToolCallFunction, ToolCallInfo
from app.services.chat.skills.registry import SkillRegistry


def _find_matching_paren(text: str, start: int) -> int:
    depth = 0
    in_str = None
    i = start
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\" and i + 1 < len(text):
                i += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c in ('"', "'"):
                in_str = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _parse_positional_args(args_text: str, param_order: list[str]) -> dict | None:
    args_text = args_text.strip()
    if not args_text:
        return {}

    try:
        parsed = json.loads(args_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    try:
        parsed = json.loads(f"[{args_text}]")
        if isinstance(parsed, list):
            return {
                param_order[i]: value
                for i, value in enumerate(parsed)
                if i < len(param_order)
            }
    except json.JSONDecodeError:
        pass

    stripped = args_text.strip()
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        stripped = stripped[1:-1]
    return {param_order[0]: stripped} if param_order else None


def extract_pseudo_tool_calls(text: str, registry: SkillRegistry) -> list[ToolCallInfo]:
    if not text:
        return []

    skills = registry.list_skills()
    names = [re.escape(s.name) for s in skills]
    if not names:
        return []

    pattern = re.compile(r"\b(" + "|".join(names) + r")\s*\(")
    calls: list[ToolCallInfo] = []

    for match in pattern.finditer(text):
        name = match.group(1)
        paren_start = match.end() - 1
        paren_end = _find_matching_paren(text, paren_start)
        if paren_end == -1:
            continue

        skill = registry.get(name)
        if skill is None:
            continue

        param_order = list(skill.parameters.get("properties", {}).keys())
        args_dict = _parse_positional_args(text[paren_start + 1:paren_end], param_order)
        if args_dict is None:
            continue

        calls.append(ToolCallInfo(
            id=f"pseudo_{len(calls)}",
            type="function",
            function=ToolCallFunction(
                name=name,
                arguments=json.dumps(args_dict, ensure_ascii=False),
            ),
        ))

    return calls
