"""Agentic Skill 结构化定义。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


@lru_cache(maxsize=512)
def _ascii_keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile ASCII word-boundary matchers once per keyword."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])")


@dataclass(frozen=True, slots=True)
class Skill:
    """定义用户意图、可用工具和互斥路由规则。"""

    name: str
    description: str
    triggers: tuple[str, ...]
    activation_keywords: tuple[str, ...]
    tool_names: tuple[str, ...]
    rules: tuple[str, ...]
    priority: int = 100
    exclusions: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    # Tools exposed on the first turn; the rest need an explicit ``load_skill``.
    # Empty means every ``tool_names`` entry is initial (legacy behavior).
    core_tool_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.name) is None:
            raise ValueError(f"Skill 名称不合法：{self.name!r}")
        if not self.description.strip():
            raise ValueError(f"Skill '{self.name}' 缺少 description")
        if not self.triggers:
            raise ValueError(f"Skill '{self.name}' 至少需要一个触发条件")
        if not self.activation_keywords:
            raise ValueError(f"Skill '{self.name}' 至少需要一个激活关键词")
        if not self.tool_names:
            raise ValueError(f"Skill '{self.name}' 至少需要一个工具")
        if not self.rules:
            raise ValueError(f"Skill '{self.name}' 至少需要一条路由规则")
        if self.priority < 0:
            raise ValueError(f"Skill '{self.name}' priority 不能小于 0")
        if len(self.tool_names) != len(set(self.tool_names)):
            raise ValueError(f"Skill '{self.name}' 包含重复工具")
        if len(self.core_tool_names) != len(set(self.core_tool_names)):
            raise ValueError(f"Skill '{self.name}' 的 core_tools 包含重复工具")
        invalid_core = sorted(set(self.core_tool_names) - set(self.tool_names))
        if invalid_core:
            raise ValueError(
                f"Skill '{self.name}' 的 core_tools 未包含在 tools 中：{invalid_core}"
            )
        for field_name, values in (
            ("triggers", self.triggers),
            ("activation_keywords", self.activation_keywords),
            ("tool_names", self.tool_names),
            ("core_tool_names", self.core_tool_names),
            ("rules", self.rules),
            ("exclusions", self.exclusions),
            ("examples", self.examples),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"Skill '{self.name}' 的 {field_name} 包含空值")

    def matches(self, message: str) -> bool:
        return self.matches_normalized(message.lower())

    @property
    def initial_tool_names(self) -> tuple[str, ...]:
        """Tools exposed on the first turn (``core_tools`` or all tools)."""
        return self.core_tool_names or self.tool_names

    def match_score(self, normalized_message: str) -> int:
        """Rank how strongly this skill matches an already-lowercased message."""
        score = 0
        for keyword in self.activation_keywords:
            normalized_keyword = keyword.lower()
            if normalized_keyword.isascii() and normalized_keyword.isalnum():
                if not _ascii_keyword_pattern(normalized_keyword).search(normalized_message):
                    continue
                score += 2  # ASCII acronyms/terms are more specific than broad Chinese words.
            elif normalized_keyword in normalized_message:
                score += 1
            else:
                continue
            if len(normalized_keyword) >= 4:
                score += 1
        return score

    def matches_normalized(self, normalized_message: str) -> bool:
        """Match against an already-lowercased message (callers can reuse it)."""
        return self.match_score(normalized_message) > 0

    def render_catalog(self, index: int, *, recommended: bool = False) -> str:
        """Compact routing entry: skill name, description and triggers."""
        marker = "[推荐] " if recommended else ""
        return "\n".join([
            f"{index}. **{marker}{self.name}** — {self.description}",
            f"- 触发：{'；'.join(self.triggers)}",
        ])

    def render_instructions(self, index: int) -> str:
        """Detailed rules/examples, loaded only when the skill is selected."""
        lines = [f"- {rule}" for rule in self.rules]
        if self.exclusions:
            lines.append(f"- 避免：{'；'.join(self.exclusions)}")
        if self.examples:
            lines.append(f"- 示范：{' | '.join(self.examples)}")
        return "\n".join(lines)

    def render_prompt(self, index: int) -> str:
        """Backward-compatible full prompt (catalog + instructions)."""
        return "\n".join(
            part
            for part in (self.render_catalog(index), self.render_instructions(index))
            if part
        )
