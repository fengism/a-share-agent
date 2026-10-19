"""Tool and skill registry."""

from __future__ import annotations

import logging
import re
from collections.abc import Collection
from typing import TYPE_CHECKING, Any

import app.agentic.tools.contracts as tool_contracts
import app.agentic.tools.serialization as tool_serialization
import app.agentic.tools.validation as tool_validation
from app.agentic.protocol import ToolCallInfo, ToolResultInfo

if TYPE_CHECKING:
    from app.agentic.runtime.context import AgentExecutionContext
    from app.agentic.skills.contracts import Skill

logger = logging.getLogger(__name__)


class CapabilityCatalog:
    """Registry for tools, execution policies, and skill prompts."""

    def __init__(self):
        self._tools: dict[str, tool_contracts.Tool] = {}
        self._skills: list[Skill] = []

    def register_tool(self, tool: tool_contracts.Tool) -> tool_contracts.Tool:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", tool.name):
            raise ValueError(f"工具名称不合法：{tool.name!r}")
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册，禁止静默覆盖")
        tool_validation.validate_schema(tool.parameters)
        tool_validation.validate_executor_contract(tool)
        self._tools[tool.name] = tool
        return tool

    def get_tool(self, name: str) -> tool_contracts.Tool | None:
        return self._tools.get(name)

    def get_tool_policy(self, name: str) -> tool_contracts.ToolPolicy | None:
        tool = self._tools.get(name)
        return tool.policy if tool is not None else None

    def list_tools(self) -> list[tool_contracts.Tool]:
        return list(self._tools.values())

    def tool_names(self) -> set[str]:
        return set(self._tools)

    def unregister_tools(self, names: Collection[str]) -> None:
        for name in names:
            self._tools.pop(name, None)

    def get_tool_definitions_for(self, tool_names: list[str]) -> list[dict]:
        selected = set(tool_names)
        return [
            tool.to_tool_definition()
            for name, tool in self._tools.items()
            if name in selected
        ]

    async def execute_tool(
        self,
        call: ToolCallInfo,
        allowed_names: Collection[str] | None = None,
        execution_context: AgentExecutionContext | None = None,
        *,
        arguments: Any | None = None,
    ) -> ToolResultInfo:
        if allowed_names is not None and call.function.name not in allowed_names:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=tool_serialization.serialize_error(
                    "tool_not_allowed",
                    f"工具 '{call.function.name}' 不在当前 Agent 的允许范围内",
                ),
                is_error=True,
            )

        tool = self._tools.get(call.function.name)
        if tool is None:
            available = ", ".join(sorted(self._tools))
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=tool_serialization.serialize_error(
                    "tool_not_found",
                    (
                        f"工具 '{call.function.name}' 不存在。"
                        f"可用工具：{available}。请从以上列表中选择正确的工具重试。"
                    ),
                ),
                is_error=True,
            )
        return await tool.execute(call, execution_context=execution_context, arguments=arguments)

    def register_skill(self, skill: Skill) -> Skill:
        if any(existing.name == skill.name for existing in self._skills):
            raise ValueError(f"Skill '{skill.name}' 已注册，禁止静默覆盖")
        missing_tools = sorted(set(skill.tool_names) - set(self._tools))
        if missing_tools:
            raise ValueError(f"Skill '{skill.name}' 引用了未注册工具：{missing_tools}")
        self._skills.append(skill)
        return skill

    def list_skills(self) -> list[Skill]:
        return sorted(self._skills, key=lambda skill: (skill.priority, skill.name))

    def skill_names(self) -> set[str]:
        return {skill.name for skill in self._skills}

    def unregister_skills(self, names: Collection[str]) -> None:
        if not names:
            return
        removed = set(names)
        self._skills = [skill for skill in self._skills if skill.name not in removed]

    def validate_skill_coverage(self) -> list[str]:
        covered_tools = {
            tool_name
            for skill in self._skills
            for tool_name in skill.tool_names
        }
        data_tools = {
            name
            for name, tool in self._tools.items()
            if tool.policy.evidence
        }
        missing_tools = sorted(data_tools - covered_tools)
        if missing_tools:
            logger.warning("以下数据工具尚未归属任何 Skill：%s", missing_tools)
        return missing_tools

    def _selected_skills(self, skill_names: Collection[str] | None = None) -> list[Skill]:
        selected = None if skill_names is None else set(skill_names)
        return [
            skill
            for skill in self.list_skills()
            if selected is None or skill.name in selected
        ]

    def get_skill_prompt(self, skill_names: Collection[str] | None = None) -> str:
        """Full prompt for backward compatibility; prefer catalog + instructions."""
        skills = self._selected_skills(skill_names)
        if not skills:
            return ""
        return "\n\n".join(
            skill.render_prompt(index)
            for index, skill in enumerate(skills, start=1)
        )

    def get_skill_catalog_prompt(
        self,
        skill_names: Collection[str] | None = None,
        *,
        active_skill_names: Collection[str] | None = None,
    ) -> str:
        """Compact catalog: descriptions and triggers, no rules/examples."""
        skills = self._selected_skills(skill_names)
        if not skills:
            return ""
        active = set(active_skill_names or ())
        return "\n\n".join(
            skill.render_catalog(index, recommended=skill.name in active)
            for index, skill in enumerate(skills, start=1)
        )

    def get_skill_instructions(
        self,
        skill_names: Collection[str] | None = None,
        *,
        limit: int | None = 1,
    ) -> str:
        """Detailed instructions for the top-N skills (priority order)."""
        skills = self._selected_skills(skill_names)
        if limit is not None:
            skills = skills[:max(0, int(limit))]
        if not skills:
            return ""
        parts = [
            f"### {skill.description}\n{skill.render_instructions(index)}"
            for index, skill in enumerate(skills, start=1)
        ]
        return "## Skill 详细规则\n\n" + "\n\n".join(parts)

    def get_tool_names_for_skills(
        self,
        skill_names: Collection[str] | None = None,
    ) -> list[str]:
        selected = None if skill_names is None else set(skill_names)
        names: list[str] = []
        seen: set[str] = set()
        for skill in self.list_skills():
            if selected is not None and skill.name not in selected:
                continue
            for tool_name in skill.tool_names:
                if tool_name in seen:
                    continue
                seen.add(tool_name)
                names.append(tool_name)
        return names

    def get_initial_tool_names_for_skills(
        self,
        skill_names: Collection[str] | None = None,
    ) -> list[str]:
        """First-turn tools: ``core_tools`` when declared, else every tool."""
        selected = None if skill_names is None else set(skill_names)
        names: list[str] = []
        seen: set[str] = set()
        for skill in self.list_skills():
            if selected is not None and skill.name not in selected:
                continue
            for tool_name in skill.initial_tool_names:
                if tool_name in seen:
                    continue
                seen.add(tool_name)
                names.append(tool_name)
        return names

registry = CapabilityCatalog()
