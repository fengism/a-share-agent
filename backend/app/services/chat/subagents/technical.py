from app.services.chat.subagents.base import SubAgent
from app.services.chat.subagents.prompts import TECHNICAL_AGENT_PROMPT


def create_technicalagent() -> SubAgent:
    """创建技术面分析 Agent 实例。

    Return:
        配置好 prompt 和 tools 的 SubAgent 实例
    """
    return SubAgent(
        name="technical",
        display_name="技术面分析",
        system_prompt=TECHNICAL_AGENT_PROMPT,
        skill_names=["search_stocks", "get_stock_kline", "get_stock_technical_indicators"],
        max_rounds=3,
    )
