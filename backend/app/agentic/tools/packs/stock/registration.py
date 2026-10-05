from __future__ import annotations

from app.agentic.catalog import registry
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.agentic.tools.packs.stock import helpers

_STOCK_CODE_SCHEMA = {
    "type": "string",
    "pattern": r"^\d{6}$",
    "description": "6位股票代码，如 600519",
}
# 港股为 1-5 位数字，与 A 股 6 位天然互斥；港股工具不能复用 A 股的代码约束。
_HK_CODE_SCHEMA = {
    "type": "string",
    "pattern": r"^(?:hk)?\d{1,5}$",
    "description": "港股代码，1-5 位数字，可省略前导 0，如 00700、700",
}
_QUERY_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "maxLength": 300,
}
_REALTIME_POLICY = ToolPolicy(cache_ttl_seconds=30, freshness="realtime")
_MEDIUM_REALTIME_POLICY = ToolPolicy(
    cost="medium",
    cache_ttl_seconds=30,
    freshness="realtime",
)
_MEDIUM_QUERY_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=60)
_DAILY_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=900, freshness="daily")
_STATIC_POLICY = ToolPolicy(cache_ttl_seconds=3600, freshness="static")
_HIGH_COST_POLICY = ToolPolicy(cost="high", cache_ttl_seconds=60)


def _register_stock_lookup_tools() -> None:
    """Register stock search and basic-information tools."""
    registry.register_tool(Tool(
        name="search_stocks",
        description="按股票名称或不完整代码搜索股票，返回代码、名称、价格和涨跌幅。仅在用户未提供完整6位代码时调用；已知完整代码可直接使用其他工具。",
        parameters={
            "type": "object",
            "properties": {
                "query": {**_QUERY_SCHEMA, "maxLength": 30, "description": "股票代码或名称关键词"},
            },
            "required": ["query"],
        },
        policy=_REALTIME_POLICY,
        executor=helpers.search_stocks,
    ))

    registry.register_tool(Tool(
        name="get_stock_info",
        description="获取股票基本信息，包括行业分类、市值、PE/PB、上市日期等。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_REALTIME_POLICY,
        executor=helpers.get_stock_info,
    ))


def _register_hk_stock_tools() -> None:
    """Register HK-specific tools.

    港股只提供行情口径的事实：A 股口径的财务、估值、情绪、资金流工具对港股无效，
    不注册以免 Agent 反复重试不存在的接口。K 线与技术指标复用同一执行器
    （``get_kline`` / ``get_technical_indicators`` 内部已按港股代码分流），
    这里只是把参数约束从 6 位 A 股代码换成港股代码。
    """
    registry.register_tool(Tool(
        name="get_hk_stock_profile",
        description="获取港股行情快照，包含名称、现价、涨跌额/幅、昨收、开盘、最高、最低、成交量与成交额。港股分析的基础事实来源。",
        parameters={
            "type": "object",
            "properties": {
                "code": _HK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_REALTIME_POLICY,
        executor=helpers.get_hk_stock_profile,
    ))

    registry.register_tool(Tool(
        name="get_hk_stock_kline",
        description="获取港股K线数据（日K/周K/月K），含开高低收、成交量等。港股无涨跌停且可做空港股，量价含义与A股不同，解读时需说明。",
        parameters={
            "type": "object",
            "properties": {
                "code": _HK_CODE_SCHEMA,
                "period": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "default": "daily",
                    "description": "K线周期，默认daily",
                },
            },
            "required": ["code"],
        },
        policy=_MEDIUM_REALTIME_POLICY,
        executor=helpers.get_stock_kline,
    ))

    registry.register_tool(Tool(
        name="get_hk_stock_technical_indicators",
        description="计算港股技术指标，包括均线、MACD、RSI、布林带、KDJ等。可指定周期（daily/weekly/monthly/annual）。",
        parameters={
            "type": "object",
            "properties": {
                "code": _HK_CODE_SCHEMA,
                "period": {
                    "type": "string",
                    "description": "K线周期：daily（日线，默认）、weekly（周线）、monthly（月线）、annual（年线）",
                    "enum": ["daily", "weekly", "monthly", "annual"],
                    "default": "daily",
                },
            },
            "required": ["code"],
        },
        policy=_MEDIUM_REALTIME_POLICY,
        executor=helpers.get_stock_technical_indicators,
    ))

    registry.register_tool(Tool(
        name="get_hk_market_overview",
        description="获取港股主要指数实时行情（恒生指数、恒生国企指数、恒生科技指数）。分析港股时的市场环境证据。",
        parameters={"type": "object", "properties": {}},
        policy=_REALTIME_POLICY,
        executor=helpers.get_hk_market_overview,
    ))


def _register_stock_analysis_tools() -> None:
    """Register valuation, technical, K-line, and financial tools."""
    registry.register_tool(Tool(
        name="get_stock_valuation_detail",
        description="获取股票详细估值分析，包含PE/PB/PS、估值百分位、同业对比、多种估值方法结果（含DCF）、机构预测等。个股分析时必调用的核心工具。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.get_stock_valuation_detail,
    ))

    registry.register_tool(Tool(
        name="get_stock_technical_indicators",
        description="计算股票技术指标，包括均线、MACD、RSI、布林带、KDJ等。可指定周期（daily/weekly/monthly/annual）。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
                "period": {
                    "type": "string",
                    "description": "K线周期：daily（日线，默认）、weekly（周线）、monthly（月线）、annual（年线）",
                    "enum": ["daily", "weekly", "monthly", "annual"],
                    "default": "daily",
                },
            },
            "required": ["code"],
        },
        policy=_MEDIUM_REALTIME_POLICY,
        executor=helpers.get_stock_technical_indicators,
    ))

    registry.register_tool(Tool(
        name="get_stock_kline",
        description="获取股票K线数据（日K/周K/月K），含开高低收、成交量等。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
                "period": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "default": "daily",
                    "description": "K线周期，默认daily",
                },
            },
            "required": ["code"],
        },
        policy=_MEDIUM_REALTIME_POLICY,
        executor=helpers.get_stock_kline,
    ))

    registry.register_tool(Tool(
        name="get_stock_financial",
        description="获取股票单类财务报表数据。仅查询一张指定报表时使用；完整财报分析优先使用 analyze_financials。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
                "indicator": {
                    "type": "string",
                    "enum": ["balance", "profit", "cashflow"],
                    "default": "balance",
                    "description": "报表类型，默认balance",
                },
            },
            "required": ["code"],
        },
        policy=_DAILY_POLICY,
        executor=helpers.get_stock_financial,
    ))


def _register_stock_news_tools() -> None:
    """Register stock news and sentiment tools."""
    registry.register_tool(Tool(
        name="get_stock_news",
        description="获取股票相关新闻列表。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.get_stock_news,
    ))

    registry.register_tool(Tool(
        name="get_stock_sentiment",
        description="获取股票情绪数据，包括热度排名、热度分数等。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_MEDIUM_REALTIME_POLICY,
        executor=helpers.get_stock_sentiment,
    ))


def _register_structured_screening_tools() -> None:
    """Register fixed-field screening and industry lookup tools."""
    registry.register_tool(Tool(
        name="screen_stocks",
        description="按固定维度筛选股票，支持PE、PB、价格、市值、涨跌幅、换手率、行业等结构化条件。仅当选股条件能精确映射到这些参数时使用（如简单的数值范围筛选）。对于自然语言选股条件，优先使用 iwencai_select_stock。",
        parameters={
            "type": "object",
            "properties": {
                "pe_min": {"type": "number", "minimum": -100000, "maximum": 100000, "description": "PE下限"},
                "pe_max": {"type": "number", "minimum": -100000, "maximum": 100000, "description": "PE上限"},
                "pb_min": {"type": "number", "minimum": -10000, "maximum": 10000, "description": "PB下限"},
                "pb_max": {"type": "number", "minimum": -10000, "maximum": 10000, "description": "PB上限"},
                "price_min": {"type": "number", "minimum": 0, "maximum": 1000000, "description": "价格下限"},
                "price_max": {"type": "number", "minimum": 0, "maximum": 1000000, "description": "价格上限"},
                "market_cap_min": {"type": "number", "minimum": 0, "maximum": 100000000, "description": "市值下限（亿元）"},
                "market_cap_max": {"type": "number", "minimum": 0, "maximum": 100000000, "description": "市值上限（亿元）"},
                "change_pct_min": {"type": "number", "minimum": -100, "maximum": 1000, "description": "涨跌幅下限(%)"},
                "change_pct_max": {"type": "number", "minimum": -100, "maximum": 1000, "description": "涨跌幅上限(%)"},
                "turnover_pct_min": {"type": "number", "minimum": 0, "maximum": 1000, "description": "换手率下限(%)"},
                "turnover_pct_max": {"type": "number", "minimum": 0, "maximum": 1000, "description": "换手率上限(%)"},
                "industries": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 50},
                    "maxItems": 20,
                    "uniqueItems": True,
                    "description": "行业列表（支持申万一级、二级、三级行业名称）",
                },
                "concepts": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 50},
                    "maxItems": 20,
                    "uniqueItems": True,
                    "description": "概念题材列表（支持按个股概念库筛选，如'高股息精选'、'人工智能'等）",
                },
                "markets": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["主板", "科创板", "创业板", "北交所"]},
                    "maxItems": 4,
                    "uniqueItems": True,
                    "description": "市场板块筛选，省略表示全部市场",
                },
                "exclude_st": {
                    "type": "boolean",
                    "default": False,
                    "description": "剔除 ST/*ST/退市风险股",
                },
                "min_listing_days": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "剔除上市不满 N 天的新股；省略表示不过滤",
                },
                "min_amount_yi": {
                    "type": "number",
                    "minimum": 0,
                    "description": "当日成交额下限（亿元），用于过滤流动性不足的标的；省略表示不过滤",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["market_cap", "pe", "pb", "price", "change_pct", "turnover_pct", "volume"],
                    "default": "market_cap",
                    "description": "排序字段，默认market_cap",
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                    "description": "排序方向，默认desc",
                },
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": "页码，从 1 开始；结果集较大时翻页获取",
                },
                "page_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                    "description": "每页条数，最大 200",
                },
            },
        },
        policy=_MEDIUM_REALTIME_POLICY,
        executor=helpers.screen_stocks,
    ))

    registry.register_tool(Tool(
        name="get_industries",
        description="获取所有行业列表，用于筛选股票时确定行业参数名称。当用户提到的行业名称不确定时先调用此工具查找。",
        parameters={"type": "object", "properties": {}},
        policy=_STATIC_POLICY,
        executor=helpers.get_industries,
    ))


def _register_iwencai_research_tools() -> None:
    registry.register_tool(Tool(
        name="iwencai_search",
        description="语义搜索研报、公告、新闻。支持自然语言查询，如'人形机器人 研报'、'贵州茅台 公告'、'半导体 利好新闻'。当用户需要查找研报、公告或新闻资讯时调用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {**_QUERY_SCHEMA, "description": "搜索关键词，支持自然语言"},
                "channel": {
                    "type": "string",
                    "enum": ["report", "announcement", "news"],
                    "default": "report",
                    "description": "搜索类型：report=研报，announcement=公告，news=新闻，默认report",
                },
                "size": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20, "description": "返回条数，默认20"},
            },
            "required": ["query"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.iwencai_search,
    ))

    registry.register_tool(Tool(
        name="iwencai_query",
        description="自然语言结构化数据查询。输入自然语言描述即可获取结构化财务/行情数据，如'贵州茅台 ROE'、'白酒行业 市值前10'、'连续3天涨停的股票'。适合用户需要用自然语言灵活查询数据时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {**_QUERY_SCHEMA, "description": "自然语言查询，如'贵州茅台 ROE'、'连续3天涨停'"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 30, "description": "返回条数，默认30"},
            },
            "required": ["query"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.iwencai_query,
    ))

    registry.register_tool(Tool(
        name="iwencai_select_stock",
        description="问财智能选股（首选选股工具）。输入自然语言选股条件即可返回符合条件的股票列表，如'今日涨跌幅大于5%'、'连续涨停的股票'、'低市盈率高增长'、'北向资金连续净买入'、'科技股有哪些'。选股场景下优先使用此工具，仅在条件无法用自然语言表达且能精确映射到结构化参数时才用 screen_stocks。",
        parameters={
            "type": "object",
            "properties": {
                "query": {**_QUERY_SCHEMA, "description": "自然语言选股条件，如'今日涨停'、'PE小于20且ROE大于15%'、'北向资金连续净买入'"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20, "description": "返回条数，默认20"},
            },
            "required": ["query"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.iwencai_select_stock,
    ))

def _register_risk_tool() -> None:
    registry.register_tool(Tool(
        name="get_stock_risk_data",
        description="获取个股风险评估数据：资金流向（主力/大单/中单/小单净流入）、融资融券明细、大宗交易记录、股东户数变化。风险评估时必调用。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_HIGH_COST_POLICY,
        executor=helpers.get_stock_risk_data,
    ))

    registry.register_tool(Tool(
        name="get_restricted_shares_lift",
        description="获取个股未来与历史限售股解禁日历、解禁类型（首发原股东/定向增发机构配售/股权激励）、解禁股数、市值及占流通盘比例，测算大股东与机构减持抛压风险。个股排雷与风险分析时调用。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
            },
            "required": ["code"],
        },
        policy=_DAILY_POLICY,
        executor=helpers.get_restricted_shares_lift,
    ))

    registry.register_tool(Tool(
        name="get_interactive_qa",
        description="获取上市公司在深交所互动易、上交所 e 互动官方平台上董秘对投资者提问的权威法定答复。支持按业务关键词（如'特斯拉''华为''机器人''算力''订单'）检索，用于官方实锤订单合作、量产进展与辟谣求证。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
                "keyword": {
                    "type": "string",
                    "description": "业务或题材搜索关键词，如'特斯拉'、'华为'、'机器人'、'订单'、'出海'；省略则返回最新问答",
                    "default": "",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 15,
                    "description": "返回条数，默认15",
                },
            },
            "required": ["code"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.get_interactive_qa,
    ))


def _register_macro_query_tool() -> None:
    registry.register_tool(Tool(
        name="iwencai_market_macro",
        description="按自然语言查询指定宏观指标、历史区间或统计口径，如GDP、CPI、PPI、M2、PMI。若只需最新常用指标汇总，使用 get_macro_data。",
        parameters={
            "type": "object",
            "properties": {
                "query": {**_QUERY_SCHEMA, "description": "自然语言宏观经济查询，如'中国GDP增速'、'M2增速'、'CPI同比'"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20, "description": "返回条数，默认20"},
            },
            "required": ["query"],
        },
        policy=_MEDIUM_QUERY_POLICY,
        executor=helpers.iwencai_market_macro,
    ))


def _register_stock_document_tool() -> None:
    registry.register_tool(Tool(
        name="get_stock_documents",
        description="按A股代码定位公司公告、定期报告与券商研报目录。支持发布日期、标题关键词筛选；公告按页读取，研报最多近24个月/3页，空结果不证明无披露。返回原文/PDF链接后必须调用web_fetch/read_pdf阅读，标题不是事实证据，发布日期不是报告期。",
        parameters={
            "type": "object",
            "properties": {
                "code": _STOCK_CODE_SCHEMA,
                "kind": {"type": "string", "enum": ["all", "announcement", "periodic_report", "research_report"], "default": "all"},
                "start_date": {"type": "string", "description": "发布日期下限YYYY-MM-DD，省略不设下限"},
                "end_date": {"type": "string", "description": "发布日期上限YYYY-MM-DD；历史研究应传分析基准日"},
                "keyword": {"type": "string", "maxLength": 100, "description": "公告/研报标题关键词（不搜索全文）"},
                "page": {"type": "integer", "minimum": 1, "maximum": 100, "default": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 20},
            },
            "required": ["code"],
        },
        policy=ToolPolicy(cost="medium", cache_ttl_seconds=0, timeout_seconds=45, max_parallel_calls=2),
        executor=helpers.get_stock_documents,
    ))


def register_stock_tools() -> None:
    """Register stock, screening, research, risk, and macro Tool groups."""
    _register_stock_document_tool()
    _register_stock_lookup_tools()
    _register_hk_stock_tools()
    _register_stock_analysis_tools()
    _register_stock_news_tools()
    _register_structured_screening_tools()
    _register_iwencai_research_tools()
    _register_risk_tool()
    _register_macro_query_tool()
