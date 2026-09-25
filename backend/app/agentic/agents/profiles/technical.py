from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.prompts import TECHNICAL_AGENT_PROMPT

PROFILE = AgentProfile(
    name="technical",
    display_name="技术面分析",
    description="分析价格趋势、技术指标和关键支撑压力",
    system_prompt=TECHNICAL_AGENT_PROMPT,
    tool_names=("financial_calculator", "get_stock_kline", "get_stock_technical_indicators"),
    skill_names=("stock_analysis", "financial_calculations"),
    max_rounds=3,
)
