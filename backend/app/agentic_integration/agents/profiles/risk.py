from app.agentic.agents.contracts import AgentProfile
from app.agentic_integration.agents.prompts import RISK_AGENT_PROMPT

PROFILE = AgentProfile(
    name="risk",
    display_name="风险评估",
    description="识别主要风险、回撤因素和风险控制位置",
    system_prompt=RISK_AGENT_PROMPT,
    tool_names=(
        "financial_calculator",
        "search_stocks",
        "get_stock_risk_data",
        "get_restricted_shares_lift",
        "get_stock_technical_indicators",
        "get_stock_valuation_detail",
    ),
    skill_names=("stock_analysis", "financial_calculations"),
    max_rounds=3,
)
