"""Agentic Skill 结构化定义。"""

from __future__ import annotations

import re
from dataclasses import dataclass


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
        for field_name, values in (
            ("triggers", self.triggers),
            ("activation_keywords", self.activation_keywords),
            ("tool_names", self.tool_names),
            ("rules", self.rules),
            ("exclusions", self.exclusions),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"Skill '{self.name}' 的 {field_name} 包含空值")

    def matches(self, message: str) -> bool:
        normalized = message.lower()
        for keyword in self.activation_keywords:
            normalized_keyword = keyword.lower()
            if normalized_keyword.isascii() and normalized_keyword.isalnum():
                pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
                if re.search(pattern, normalized):
                    return True
            elif normalized_keyword in normalized:
                return True
        return False

    def render_prompt(self, index: int) -> str:
        lines = [
            f"{index}. **{self.description}**",
            f"- 触发：{'；'.join(self.triggers)}",
        ]
        lines.extend(f"- {rule}" for rule in self.rules)
        if self.exclusions:
            lines.append(f"- 避免：{'；'.join(self.exclusions)}")
        return "\n".join(lines)
