from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.models.chat import ToolCallInfo, ToolResultInfo

if TYPE_CHECKING:
    from app.services.chat.skills.skill import Skill

logger = logging.getLogger(__name__)

_MAX_RESULT_LEN = 12000


def _serialize_result(result: Any) -> str:
    """将工具结果序列化为 JSON 字符串，超长时智能裁剪以保持合法 JSON。

    Param:
        result: 工具 executor 返回的任意结果
    Return:
        JSON 字符串；list 超长时按条数裁剪并附 _truncated 标记，其他类型回退为字符串截断
    """
    content = json.dumps(result, ensure_ascii=False, default=str)
    if len(content) <= _MAX_RESULT_LEN:
        return content

    # list 结果：按条数二分裁剪，保证返回的仍是合法 JSON
    if isinstance(result, list) and result:
        total = len(result)
        kept = total
        while kept > 1:
            kept = kept // 2
            payload = {
                "_truncated": f"共 {total} 条，已截断为前 {kept} 条",
                "items": result[:kept],
            }
            content = json.dumps(payload, ensure_ascii=False, default=str)
            if len(content) <= _MAX_RESULT_LEN:
                return content
        # 单条仍超长，退回字符串截断
        single = json.dumps(result[0], ensure_ascii=False, default=str)
        return single[:_MAX_RESULT_LEN] + '...(单条结果过长已截断)'

    # 非 list：字符串截断
    return content[:_MAX_RESULT_LEN] + "...(truncated)"


class Tool:
    """一个可注册的工具，自动转换为 OpenAI function calling 工具定义。"""

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
                content=f"Tool '{self.name}' has no executor",
                is_error=True,
            )
        try:
            args = json.loads(call.function.arguments)
            result = await self.executor(**args)
            content = _serialize_result(result)
            return ToolResultInfo(tool_call_id=call.id, name=call.function.name, content=content)
        except Exception as e:
            logger.error(f"Tool execution failed: {self.name}, error={e}", exc_info=True)
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=f"Error: {e}",
                is_error=True,
            )


class ChatRegistry:
    """工具与技能注册中心，管理 Tool 的注册、查询、执行，以及 Skill 的自然语言指令。"""

    def __init__(self):
        """初始化空的工具和技能容器。"""
        self._tools: dict[str, Tool] = {}
        self._skills: list[Skill] = []

    # ── Tool 管理 ──

    def register_tool(self, tool: Tool) -> Tool:
        """注册一个工具，同名工具会被覆盖。

        Param:
            tool: 要注册的 Tool 实例
        Return:
            注册的 Tool 实例
        """
        if tool.name in self._tools:
            logger.debug(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        return tool

    def get_tool(self, name: str) -> Tool | None:
        """根据名称获取工具。

        Param:
            name: 工具名称
        Return:
            对应的 Tool 实例，未找到返回 None
        """
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """返回所有已注册工具的列表。

        Param:
            无（self）
        Return:
            Tool 实例列表
        """
        return list(self._tools.values())

    def get_tool_definitions(self) -> list[dict]:
        """获取所有工具的 OpenAI 工具定义列表。

        Param:
            无（self）
        Return:
            工具定义字典列表
        """
        return [tool.to_tool_definition() for tool in self._tools.values()]

    def get_tool_definitions_for(self, tool_names: list[str]) -> list[dict]:
        """获取指定工具名称列表的 OpenAI 工具定义。

        Param:
            tool_names: 需要获取定义的工具名称列表
        Return:
            匹配的工具定义字典列表
        """
        return [
            tool.to_tool_definition()
            for name, tool in self._tools.items()
            if name in tool_names
        ]

    async def execute_tool(self, call: ToolCallInfo) -> ToolResultInfo:
        """根据工具调用信息查找工具并执行。

        Param:
            call: 工具调用信息
        Return:
            ToolResultInfo 对象，工具不存在时返回错误信息
        """
        tool = self._tools.get(call.function.name)
        if tool is None:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=f"Unknown tool: {call.function.name}",
                is_error=True,
            )
        return await tool.execute(call)

    # ── Skill 管理 ──

    def register_skill(self, skill: Skill) -> Skill:
        """注册一个技能描述，同名技能会被覆盖。

        Param:
            skill: 要注册的 Skill 实例
        Return:
            注册的 Skill 实例
        """
        # 同名替换：移除旧的
        self._skills = [s for s in self._skills if s.name != skill.name]
        self._skills.append(skill)
        return skill

    def get_skill_prompt(self) -> str:
        """拼接所有 Skill 为一段文本，自动编号，用于注入 system prompt。

        每条 Skill 输出格式：编号. **description**\nusage

        Param:
            无（self）
        Return:
            拼接后的技能选择策略文本，无技能时返回空字符串
        """
        if not self._skills:
            return ""
        parts = [
            f"{i}. **{s.description}**\n{s.usage}"
            for i, s in enumerate(self._skills, start=1)
        ]
        return "\n\n".join(parts)


# 全局注册中心
registry = ChatRegistry()
