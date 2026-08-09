from app.agentic.skills.contracts import Skill

SKILLS = (
    Skill(
        name="market_data",
        description="大盘、龙虎榜、复盘与宏观数据",
        triggers=("大盘、指数、成交额、龙虎榜或市场复盘", "CPI、PPI、PMI、GDP、M2等宏观指标"),
        tool_names=(
            "get_market_overview",
            "get_dragon_tiger",
            "get_daily_review",
            "get_macro_data",
            "iwencai_market_macro",
        ),
        rules=(
            "实时指数和成交额用 get_market_overview；龙虎榜用 get_dragon_tiger；市场总结用 get_daily_review。",
            "最新常用宏观指标汇总用 get_macro_data；指定指标、历史区间或口径用 iwencai_market_macro。",
        ),
        exclusions=("同一宏观问题不要同时调用两个宏观工具",),
        priority=60,
    ),
)
