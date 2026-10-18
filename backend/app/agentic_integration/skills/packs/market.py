from app.agentic.skills.contracts import Skill

SKILLS = (
    Skill(
        name="market_data",
        description="大盘、龙虎榜、复盘与宏观数据（支持A股与港股核心指数）",
        triggers=(
            "大盘、指数、成交额、龙虎榜或市场复盘",
            "港股大盘、恒生指数、国企指数或恒生科技指数",
            "CPI、PPI、PMI、GDP、M2等宏观指标",
            "美债收益率、中美利差、美元指数与离岸人民币汇率",
            "今日主线、主线机会或市场风格",
            "板块成分股与实时行情",
        ),
        activation_keywords=(
            "大盘", "指数", "成交额", "龙虎榜", "市场复盘", "cpi", "ppi", "pmi",
            "gdp", "m0", "m1", "m2", "宏观", "通胀", "通缩", "降准", "降息",
            "美债", "中美利差", "美元指数", "汇率", "cnh", "cny", "折现率",
            "主线", "题材", "风口", "风格", "成分股", "板块",
            "港股大盘", "恒生指数", "恒指", "恒生科技", "国企指数",
        ),
        tool_names=(
            "get_market_overview",
            "get_dragon_tiger",
            "get_daily_review",
            "get_macro_data",
            "get_global_macro_rates",
            "iwencai_market_macro",
            "get_market_mainline",
            "get_industry_rankings",
            "get_sector_stocks_history",
            "get_commodity_spot_prices",
            "get_customs_trade_data",
            "get_hk_market_overview",
        ),
        rules=(
            "A股实时指数和成交额用 get_market_overview；港股核心指数（恒指/国指/恒科）用 get_hk_market_overview；龙虎榜用 get_dragon_tiger；市场总结用 get_daily_review。",
            "最新常用宏观指标汇总用 get_macro_data；指定指标、历史区间或口径用 iwencai_market_macro。",
            "今日主线题材、龙头股和风格判断用 get_market_mainline；板块领涨和资金排行用 get_industry_rankings（code 字段即开盘红板块 ID）。",
            "板块成分股用 get_sector_stocks_history，历史日期返回历史详情；当天使用最近历史交易日成分名单并补充实时行情。plate_id 先从 get_industry_rankings 结果中获取。",
        ),
        exclusions=("同一宏观问题不要同时调用两个宏观工具",),
        examples=(
            "今日大盘成交额与涨跌家数 ➔ get_market_overview()",
            "港股大盘与恒生科技指数表现 ➔ get_hk_market_overview()",
            "今日主线题材与风口领涨龙头 ➔ get_market_mainline()",
            "近半年CPI与PPI通胀走势 ➔ get_macro_data()",
        ),
        priority=60,
    ),
)
