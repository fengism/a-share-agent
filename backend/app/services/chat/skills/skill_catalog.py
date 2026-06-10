"""Skill 目录：定义什么场景下使用哪些 Tool。

由系统自动注入到 system prompt 中，编号由 ChatRegistry.get_skill_prompt() 自动生成。
"""

from __future__ import annotations

from app.services.chat.skills.skill import Skill
from app.services.chat.tools.registry import registry

_STOCK_QUERY = Skill(
    name="stock_query",
    description="用户提到股票名称/代码时，先确认准确代码，再按意图选择对应分析工具",
    usage="""先 search_stocks 确认准确代码，再根据意图选择：
- 深度分析 / 全面评估 → analyze_stock
- 多股对比 → compare_stocks
- K 线 / 技术面 → get_stock_kline 或 get_stock_technical_indicators
- 财报 / 基本面 → get_stock_financial 或 get_stock_valuation_detail
- 新闻 / 研报 / 公告 → get_stock_news 或 iwencai_search
- 情绪 / 热度 → get_stock_sentiment""",
)

_STOCK_SCREENING = Skill(
    name="stock_screening",
    description="用户提到选股条件时，优先使用问财自然语言选股",
    usage="""优先 iwencai_select_stock：
- 支持自然语言选股，覆盖面广，如"连续涨停""北向资金净买入""低估值高增长""PE 小于 20 的白酒股"
- 仅当条件能精确映射到固定参数且问财不可用时，才使用 screen_stocks""",
)

_INDUSTRY_SECTOR = Skill(
    name="industry_sector",
    description="用户问行业/板块/题材时，按需选择分析、热度或研报工具",
    usage="""根据意图选择：
- 行业综合分析 → sector_analysis
- 热门概念 / 热门行业 / 热门股 → get_hot_rank
- 相关研报、新闻、公告 → iwencai_search""",
)

_MARKET_OVERVIEW = Skill(
    name="market_overview",
    description="用户问大盘/市场时，按需查询指数、龙虎榜、复盘或宏观数据",
    usage="""根据意图选择：
- 指数和成交额 → get_market_overview
- 龙虎榜 → get_dragon_tiger
- 每日复盘 / 市场总结 → get_daily_review
- 宏观指标（GDP、CPI、M2、PMI 等）→ iwencai_market_macro""",
)

_NATURAL_LANGUAGE_QUERY = Skill(
    name="natural_language_query",
    description="自然语言结构化数据查询，按查询类型选择对应工具",
    usage="""根据查询类型选择：
- 个股、行业、财务、行情等灵活查询 → iwencai_query
- 选股类自然语言查询 → iwencai_select_stock（不要用 iwencai_query 代替）""",
)

_URL_HANDLING = Skill(
    name="url_handling",
    description="用户发送 URL 链接时，获取网页内容并直接总结",
    usage="""网页内容获取和总结 → fetch_url
获取内容后直接对正文进行总结，不要再次调用其他工具。""",
)


def register_skill_catalog():
    """注册全部 Skill。"""
    for skill in [
        _STOCK_QUERY,
        _STOCK_SCREENING,
        _INDUSTRY_SECTOR,
        _MARKET_OVERVIEW,
        _NATURAL_LANGUAGE_QUERY,
        _URL_HANDLING,
    ]:
        registry.register_skill(skill)
