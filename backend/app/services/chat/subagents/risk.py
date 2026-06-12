from app.services.chat.subagents.base import SubAgent
from app.services.chat.subagents.prompts import RISK_AGENT_PROMPT


def create_riskagent() -> SubAgent:
    """创建风险评估 Agent 实例。

    Return:
        配置好 prompt 和 tools 的 SubAgent 实例
    """
    return SubAgent(
        name="risk",
        display_name="风险评估",
        system_prompt=RISK_AGENT_PROMPT,
        skill_names=["get_stock_risk_data", "get_stock_technical_indicators", "get_stock_valuation_detail"],
        max_rounds=3,
    )
