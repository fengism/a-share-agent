from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.prompts import MACRO_AGENT_PROMPT

PROFILE = AgentProfile(
    name="macro",
    display_name="宏观分析",
    description="分析宏观环境及其对相关股票或板块的影响",
    system_prompt=MACRO_AGENT_PROMPT,
    tool_names=("get_macro_data",),
    max_rounds=3,
)
