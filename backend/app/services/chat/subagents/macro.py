from app.services.chat.subagents.base import SubAgent
from app.services.chat.subagents.prompts import MACRO_AGENT_PROMPT


def create_macro_agent() -> SubAgent:
    """创建宏观经济分析 Agent 实例。

    Return:
        配置好 prompt 和 tools 的 SubAgent 实例
    """
    return SubAgent(
        name="macro",
        display_name="宏观分析",
        system_prompt=MACRO_AGENT_PROMPT,
        skill_names=["get_macro_data"],
        max_rounds=3,
    )
