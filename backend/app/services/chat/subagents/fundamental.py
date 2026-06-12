from app.services.chat.subagents.base import SubAgent
from app.services.chat.subagents.prompts import FUNDAMENTAL_AGENT_PROMPT


def create_fundamentalagent() -> SubAgent:
    """创建基本面分析 Agent 实例。

    Return:
        配置好 prompt 和 tools 的 SubAgent 实例
    """
    return SubAgent(
        name="fundamental",
        display_name="基本面分析",
        system_prompt=FUNDAMENTAL_AGENT_PROMPT,
        skill_names=["get_stock_valuation_detail", "get_stock_financial"],
        max_rounds=3,
    )
