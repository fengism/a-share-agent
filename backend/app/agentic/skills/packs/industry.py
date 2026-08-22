from app.agentic.skills.contracts import Skill

SKILLS = (
    Skill(
        name="industry_research",
        description="行业、板块与题材研究",
        triggers=("行业、板块或题材分析", "行业热度、成分股或相关研报"),
        activation_keywords=("行业", "板块", "题材", "产业链"),
        tool_names=("sector_analysis", "get_hot_rank", "iwencai_search"),
        rules=(
            "行业或产业链综合分析用 sector_analysis；仅看热度排名用 get_hot_rank。",
            "仅查研报、公告或新闻时用 iwencai_search。",
        ),
        exclusions=("单一问题不要同时调用综合分析和其组成工具",),
        priority=50,
    ),
)
