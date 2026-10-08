from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.prompts import FUNDAMENTAL_AGENT_PROMPT

PROFILE = AgentProfile(
    name="fundamental",
    display_name="基本面分析",
    description="分析财务质量、成长性和估值水平",
    system_prompt=FUNDAMENTAL_AGENT_PROMPT,
    tool_names=(
        "financial_calculator",
        "get_stock_info",
        "get_stock_valuation_detail",
        "analyze_financials",
        "get_stock_financial",
        "get_interactive_qa",
        "compare_stocks",
        "iwencai_select_stock",
        "screen_stocks",
        "get_industries",
        "iwencai_query",
        "get_hk_stock_profile",
        "get_hk_stock_industry_comparison",
    ),
    skill_names=("stock_analysis", "stock_screening", "financial_calculations"),
    max_rounds=3,
)
