from app.services.chat.subagents.base import SubAgent
from app.services.chat.subagents.prompts import NEWS_AGENT_PROMPT


def create_newsagent() -> SubAgent:
    """创建新闻情绪分析 Agent 实例。

    Return:
        配置好 prompt 和 tools 的 SubAgent 实例
    """
    return SubAgent(
        name="news",
        display_name="新闻情绪分析",
        system_prompt=NEWS_AGENT_PROMPT,
        skill_names=["search_stocks", "get_stock_news", "get_stock_sentiment", "iwencai_search"],
        max_rounds=3,
    )
