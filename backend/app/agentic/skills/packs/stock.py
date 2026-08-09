from app.agentic.skills.contracts import Skill

SKILLS = (
    Skill(
        name="stock_analysis",
        description="个股识别、查询与分析",
        triggers=("股票名称或6位代码", "个股估值、技术面、财报、风险或多股对比"),
        tool_names=(
            "search_stocks",
            "get_stock_info",
            "get_stock_valuation_detail",
            "get_stock_technical_indicators",
            "get_stock_kline",
            "get_stock_financial",
            "get_stock_news",
            "get_stock_sentiment",
            "get_stock_risk_data",
            "analyze_stock",
            "analyze_financials",
            "compare_stocks",
        ),
        rules=(
            "完整6位代码直接使用；仅有名称或代码不完整时先调用一次 search_stocks。",
            "全面分析用 analyze_stock；完整财报分析用 analyze_financials；多股横向比较用 compare_stocks。",
            "仅问单一维度时调用对应单项工具，不升级为全面分析。",
        ),
        exclusions=("调用组合工具后不要重复调用其组成工具", "已确认代码后不要再次搜索"),
        priority=30,
    ),
    Skill(
        name="stock_screening",
        description="条件选股与固定维度筛选",
        triggers=("选股、筛选股票", "市盈率、市净率、涨跌幅、行业等条件组合"),
        tool_names=("iwencai_select_stock", "screen_stocks", "get_industries"),
        rules=(
            "自然语言或复杂条件优先用 iwencai_select_stock。",
            "条件可精确映射到固定字段时才用 screen_stocks；行业名称不确定时先用 get_industries。",
        ),
        exclusions=("不要用 iwencai_query 代替选股", "同一条件不要同时调用两种选股工具"),
        priority=40,
    ),
)
