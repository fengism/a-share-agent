from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.models.chat import ToolCallInfo, ToolResultInfo

logger = logging.getLogger(__name__)

_MAX_RESULT_LEN = 12000


class Skill:
    """一个可注册的技能，自动转换为 OpenAI function calling 工具定义。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        executor: Callable[..., Awaitable[Any]] | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.executor = executor

    def to_tool_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, call: ToolCallInfo) -> ToolResultInfo:
        if self.executor is None:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=f"Skill '{self.name}' has no executor",
                is_error=True,
            )
        try:
            args = json.loads(call.function.arguments)
            result = await self.executor(**args)
            content = json.dumps(result, ensure_ascii=False, default=str)
            if len(content) > _MAX_RESULT_LEN:
                content = content[:_MAX_RESULT_LEN] + "...(truncated)"
            return ToolResultInfo(tool_call_id=call.id, name=call.function.name, content=content)
        except Exception as e:
            logger.error(f"Skill execution failed: {self.name}, error={e}", exc_info=True)
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=f"Error: {e}",
                is_error=True,
            )


class SkillRegistry:
    """技能注册中心，管理所有 skill 的注册、查询和执行。"""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        if skill.name in self._skills:
            logger.debug(f"Skill '{skill.name}' already registered, overwriting")
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get_tool_definitions(self) -> list[dict]:
        return [skill.to_tool_definition() for skill in self._skills.values()]

    async def execute(self, call: ToolCallInfo) -> ToolResultInfo:
        skill = self._skills.get(call.function.name)
        if skill is None:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=f"Unknown skill: {call.function.name}",
                is_error=True,
            )
        return await skill.execute(call)


# 全局注册中心
registry = SkillRegistry()
