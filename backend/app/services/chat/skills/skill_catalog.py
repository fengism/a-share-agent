"""Skill 目录：定义什么场景下使用哪些 Tool。

由系统自动注入到 system prompt 中，编号由 ChatRegistry.get_skill_prompt() 自动生成。

设计原则：
- 只保留 tool 定义中无法体现的「路由逻辑」和「组合策略」
- 不重复 tool description 中已有的用途说明
- 每条 Skill 控制在 3-5 行以内，减少 token 开销
"""

from __future__ import annotations

from app.services.chat.skills.skill import Skill
from app.services.chat.tools.registry import registry

_STOCK_QUERY = Skill(
    name="stock_query",
    description="用户提到股票名称/代码时，按意图选择对应分析工具",
    usage="""路由规则：
- 已知6位代码 → 直接使用，不调 search_stocks
- 仅给名称 → 先 search_stocks 确认代码
- 深度分析/全面评估 → analyze_stock（一次调用获取全维度数据）
- 财报分析/财务分析/利润表/资产负债表/现金流量表 → analyze_financials
- 多股对比 → compare_stocks
- 单维度查询 → 按意图选对应工具""",
)

_STOCK_SCREENING = Skill(
    name="stock_screening",
    description="用户提到选股条件时，优先使用问财自然语言选股",
    usage="优先 iwencai_select_stock（自然语言）；仅当条件精确映射到固定参数且问财不可用时，才用 screen_stocks。",
)

_INDUSTRY_SECTOR = Skill(
    name="industry_sector",
    description="用户问行业/板块/题材时，按需选择分析、热度或研报工具",
    usage="行业综合分析 → sector_analysis；热门概念/行业/股 → get_hot_rank；研报新闻 → iwencai_search。",
)

_MARKET_OVERVIEW = Skill(
    name="market_overview",
    description="用户问大盘/市场时，按需查询指数、龙虎榜、复盘或宏观数据",
    usage="指数成交额 → get_market_overview；龙虎榜 → get_dragon_tiger；复盘 → get_daily_review；宏观指标 → iwencai_market_macro。",
)

_NATURAL_LANGUAGE_QUERY = Skill(
    name="natural_language_query",
    description="自然语言结构化数据查询，按查询类型选择对应工具",
    usage="灵活数据查询 → iwencai_query；选股类查询 → iwencai_select_stock（不要用 iwencai_query 代替）。",
)

_URL_HANDLING = Skill(
    name="url_handling",
    description="用户发送 URL 链接时，获取网页内容并总结。支持新闻、博客、研报、Twitter/X 等",
    usage="fetch_url 获取正文 → 直接总结要点。不调用股票工具。获取失败如实告知。",
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
