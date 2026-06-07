from __future__ import annotations

from app.services.chat.skills import stock_helpers as helpers
from app.services.chat.skills.registry import Skill, registry


def register_stock_skills():
    """注册个股与选股相关技能：search_stocks、get_stock_info、get_stock_valuation_detail、get_stock_technical_indicators、get_stock_kline、get_stock_financial、get_stock_news、get_stock_sentiment、screen_stocks、get_industries、iwencai_search、iwencai_query、iwencai_select_stock、iwencai_market_macro。"""
    registry.register(Skill(
        name="search_stocks",
        description="搜索股票，支持按代码或名称模糊搜索。返回匹配的股票列表（代码、名称、价格、涨跌幅）。用户提到任何股票名称或代码时必须先调用此工具确认准确代码。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "股票代码或名称关键词"},
            },
            "required": ["query"],
        },
        executor=helpers.search_stocks,
    ))

    registry.register(Skill(
        name="get_stock_info",
        description="获取股票基本信息，包括行业分类、市值、PE/PB、上市日期等。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 600519"},
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_info,
    ))

    registry.register(Skill(
        name="get_stock_valuation_detail",
        description="获取股票详细估值分析，包含PE/PB/PS、估值百分位、同业对比、多种估值方法结果（含DCF）、机构预测等。个股分析时必调用的核心工具。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码"},
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_valuation_detail,
    ))

    registry.register(Skill(
        name="get_stock_technical_indicators",
        description="计算股票技术指标，包括均线、MACD、RSI、布林带、KDJ等。个股分析时必调用的核心工具。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码"},
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_technical_indicators,
    ))

    registry.register(Skill(
        name="get_stock_kline",
        description="获取股票K线数据（日K/周K/月K），含开高低收、成交量等。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码"},
                "period": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "description": "K线周期，默认daily",
                },
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_kline,
    ))

    registry.register(Skill(
        name="get_stock_financial",
        description="获取股票财务报表数据（资产负债表/利润表/现金流量表）。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码"},
                "indicator": {
                    "type": "string",
                    "enum": ["balance", "profit", "cashflow"],
                    "description": "报表类型，默认balance",
                },
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_financial,
    ))

    registry.register(Skill(
        name="get_stock_news",
        description="获取股票相关新闻列表。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码"},
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_news,
    ))

    registry.register(Skill(
        name="get_stock_sentiment",
        description="获取股票情绪数据，包括热度排名、热度分数等。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码"},
            },
            "required": ["code"],
        },
        executor=helpers.get_stock_sentiment,
    ))

    registry.register(Skill(
        name="screen_stocks",
        description="按固定维度筛选股票，支持PE、PB、价格、市值、涨跌幅、换手率、行业等结构化条件。仅当选股条件能精确映射到这些参数时使用（如简单的数值范围筛选）。对于自然语言选股条件，优先使用 iwencai_select_stock。",
        parameters={
            "type": "object",
            "properties": {
                "pe_min": {"type": "number", "description": "PE下限"},
                "pe_max": {"type": "number", "description": "PE上限"},
                "pb_min": {"type": "number", "description": "PB下限"},
                "pb_max": {"type": "number", "description": "PB上限"},
                "price_min": {"type": "number", "description": "价格下限"},
                "price_max": {"type": "number", "description": "价格上限"},
                "market_cap_min": {"type": "number", "description": "市值下限（亿元）"},
                "market_cap_max": {"type": "number", "description": "市值上限（亿元）"},
                "change_pct_min": {"type": "number", "description": "涨跌幅下限(%)"},
                "change_pct_max": {"type": "number", "description": "涨跌幅上限(%)"},
                "turnover_pct_min": {"type": "number", "description": "换手率下限(%)"},
                "turnover_pct_max": {"type": "number", "description": "换手率上限(%)"},
                "industries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "行业列表",
                },
                "sort_by": {"type": "string", "description": "排序字段，默认market_cap"},
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "排序方向，默认desc",
                },
            },
        },
        executor=helpers.screen_stocks,
    ))

    registry.register(Skill(
        name="get_industries",
        description="获取所有行业列表，用于筛选股票时确定行业参数名称。当用户提到的行业名称不确定时先调用此工具查找。",
        parameters={"type": "object", "properties": {}},
        executor=helpers.get_industries,
    ))

    registry.register(Skill(
        name="iwencai_search",
        description="语义搜索研报、公告、新闻。支持自然语言查询，如'人形机器人 研报'、'贵州茅台 公告'、'半导体 利好新闻'。当用户需要查找研报、公告或新闻资讯时调用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，支持自然语言"},
                "channel": {
                    "type": "string",
                    "enum": ["report", "announcement", "news"],
                    "description": "搜索类型：report=研报，announcement=公告，news=新闻，默认report",
                },
                "size": {"type": "integer", "description": "返回条数，默认20"},
            },
            "required": ["query"],
        },
        executor=helpers.iwencai_search,
    ))

    registry.register(Skill(
        name="iwencai_query",
        description="自然语言结构化数据查询。输入自然语言描述即可获取结构化财务/行情数据，如'贵州茅台 ROE'、'白酒行业 市值前10'、'连续3天涨停的股票'。适合用户需要用自然语言灵活查询数据时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询，如'贵州茅台 ROE'、'连续3天涨停'"},
                "limit": {"type": "integer", "description": "返回条数，默认30"},
            },
            "required": ["query"],
        },
        executor=helpers.iwencai_query,
    ))

    registry.register(Skill(
        name="iwencai_select_stock",
        description="问财智能选股（首选选股工具）。输入自然语言选股条件即可返回符合条件的股票列表，如'今日涨跌幅大于5%'、'连续涨停的股票'、'低市盈率高增长'、'北向资金连续净买入'、'科技股有哪些'。选股场景下优先使用此工具，仅在条件无法用自然语言表达且能精确映射到结构化参数时才用 screen_stocks。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言选股条件，如'今日涨停'、'PE小于20且ROE大于15%'、'北向资金连续净买入'"},
                "limit": {"type": "integer", "description": "返回条数，默认20"},
            },
            "required": ["query"],
        },
        executor=helpers.iwencai_select_stock,
    ))

    registry.register(Skill(
        name="iwencai_market_macro",
        description="问财宏观经济数据查询。输入自然语言查询宏观经济指标，如GDP、CPI、PPI、M2、PMI等，如'2024年中国GDP增速'、'最近一期CPI'、'M2增速'。当用户询问宏观经济数据、经济指标时调用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言宏观经济查询，如'中国GDP增速'、'M2增速'、'CPI同比'"},
                "limit": {"type": "integer", "description": "返回条数，默认20"},
            },
            "required": ["query"],
        },
        executor=helpers.iwencai_market_macro,
    ))
