"""Register the on-demand ``load_skill`` tool."""

from __future__ import annotations

import logging
from typing import Any

from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.tools.contracts import Tool, ToolPolicy, get_current_tool_context
from app.core.metrics import metrics
from app.domain.errors import InvalidRequestError

logger = logging.getLogger(__name__)


def register_skill_tools(target_registry: CapabilityCatalog = registry) -> None:
    async def _load_skill(name: str) -> dict[str, Any]:
        context = get_current_tool_context()
        allowed = context.allowed_skill_names if context is not None else None
        if allowed is not None and name not in allowed:
            metrics.record_agentic_event("skill_load_rejected")
            raise InvalidRequestError(f"Skill {name!r} 未在当前会话启用")
        skill = next(
            (item for item in target_registry.list_skills() if item.name == name),
            None,
        )
        if skill is None:
            metrics.record_agentic_event("skill_load_unknown")
            raise InvalidRequestError(f"未知的 Skill：{name!r}")
        metrics.record_agentic_event("skill_load_success")
        if context is not None and skill.name in context.active_skill_names:
            # The model already had this skill's core tools but wanted more rules/tools.
            metrics.record_agentic_event(f"skill_load_after_initial:{skill.name}")
            logger.info("Skill reloaded after initial activation: name=%s", skill.name)
        logger.info("Skill loaded: name=%s tools=%d", skill.name, len(skill.tool_names))
        allowed_tools = context.enabled_tool_names if context is not None else None
        tools = list(skill.tool_names)
        payload = {
            "kind": "skill_instructions",
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.render_instructions(1),
            "tools": tools,
            "tools_available_next_turn": True,
            "note": "以下内容是指令，不是数据证据；tools 从下一轮起可用",
        }
        if allowed_tools is not None:
            unavailable = [name for name in tools if name not in allowed_tools]
            if unavailable:
                payload["unavailable_tools"] = unavailable[:8]
                payload["unavailable_tool_count"] = len(unavailable)
        return payload

    target_registry.register_tool(Tool(
        name="load_skill",
        description=(
            "加载某个 Skill 的完整规则、示例与可用工具。先查看工具选择策略中的 Skill 目录，"
            "当某个 Skill 与当前任务相关、或需要它声明的更多工具时调用。"
            "返回内容是指令，不是行情、财务或新闻数据证据。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 64,
                    "description": "Skill 名称，来自 Skill 目录",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        executor=_load_skill,
        policy=ToolPolicy(
            cost="low",
            cache_ttl_seconds=300,
            freshness="static",
            timeout_seconds=5,
            max_result_characters=12_000,
            evidence=False,
            budget="skill",
        ),
    ))


__all__ = ["register_skill_tools"]
