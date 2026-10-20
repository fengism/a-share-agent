from app.agentic.agents.contracts import AgentProfile
from app.agentic_integration.agents.prompts import NEWS_AGENT_PROMPT

PROFILE = AgentProfile(
    name="news",
    display_name="新闻情绪分析",
    description="分析近期新闻、公告和市场情绪",
    system_prompt=NEWS_AGENT_PROMPT,
    tool_names=(
        "search_stocks",
        "get_stock_news",
        "get_stock_sentiment",
        "get_interactive_qa",
        "iwencai_search",
        "web_search",
        "web_fetch",
        "fetch_urls",
        "read_pdf",
    ),
    skill_names=("stock_analysis", "information_query", "url_content"),
    max_rounds=3,
)
