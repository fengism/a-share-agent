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
        """转换为 OpenAI function calling 工具定义格式。

        Param:
            无（self）
        Return:
            符合 OpenAI tools 字段格式的字典
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, call: ToolCallInfo) -> ToolResultInfo:
        """执行工具调用，解析参数后调用 executor 并返回序列化结果。

        Param:
            call: 工具调用信息，包含 id、函数名和参数 JSON 字符串
        Return:
            ToolResultInfo 对象，包含 tool_call_id、name、content 和 is_error
        """
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
        """初始化空的技能字典。"""
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        """注册一个 skill，同名 skill 会被覆盖。

        Param:
            skill: 要注册的 Skill 实例
        Return:
            注册的 Skill 实例
        """
        if skill.name in self._skills:
            logger.debug(f"Skill '{skill.name}' already registered, overwriting")
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> Skill | None:
        """根据名称获取 skill。

        Param:
            name: skill 名称
        Return:
            对应的 Skill 实例，未找到返回 None
        """
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        """返回所有已注册 skill 的列表。

        Param:
            无（self）
        Return:
            Skill 实例列表
        """
        return list(self._skills.values())

    def get_tool_definitions(self) -> list[dict]:
        """获取所有 skill 的 OpenAI 工具定义列表。

        Param:
            无（self）
        Return:
            工具定义字典列表
        """
        return [skill.to_tool_definition() for skill in self._skills.values()]

    def get_tool_definitions_for(self, skill_names: list[str]) -> list[dict]:
        """获取指定 skill 名称列表的 OpenAI 工具定义。

        Param:
            skill_names: 需要获取定义的 skill 名称列表
        Return:
            匹配的工具定义字典列表
        """
        return [
            skill.to_tool_definition()
            for name, skill in self._skills.items()
            if name in skill_names
        ]

    async def execute(self, call: ToolCallInfo) -> ToolResultInfo:
        """根据工具调用信息查找 skill 并执行。

        Param:
            call: 工具调用信息
        Return:
            ToolResultInfo 对象，skill 不存在时返回错误信息
        """
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
