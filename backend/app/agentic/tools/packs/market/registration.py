"""市场数据 Tool 注册。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.agentic.catalog import registry
from app.agentic.tools.application import get_application_tool_handlers
from app.agentic.tools.contracts import Tool, ToolPolicy

_MARKET_REALTIME_POLICY = ToolPolicy(cache_ttl_seconds=15, freshness="realtime")
_HOT_RANK_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=30, freshness="realtime")
_MARKET_DAILY_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=300, freshness="daily")
_REVIEW_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=300,
    freshness="daily",
    scope="user",
)
_MACRO_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=3600, freshness="daily")


async def _get_market_overview() -> Any:
    """获取大盘概览，并行获取主要指数行情和两市成交额。"""
    from app.market_data.market.public import get_indices, get_market_volume
    indices, volume = await asyncio.gather(
        get_indices(),
        get_market_volume(),
        return_exceptions=True,
    )
    result: dict[str, Any] = {}
    if not isinstance(indices, Exception) and indices is not None:
        result["indices"] = indices.model_dump()
    if not isinstance(volume, Exception) and volume is not None:
        result["volume"] = volume
    return result


async def _get_hot_rank(type: str = "stocks") -> Any:
    """获取热门排名数据，根据 type 返回热门概念/行业/股票。

    Param:
        type: 热门类型，concepts=热门概念，industries=热门行业，其他=热门股票
    Return:
        对应类型的热门排名数据
    """
    from app.market_data.market.public import get_hot_stocks, get_ths_hot_concept, get_ths_hot_industry
    if type == "concepts":
        return await get_ths_hot_concept()
    if type == "industries":
        return await get_ths_hot_industry()
    return await get_hot_stocks()


async def _get_dragon_tiger(date: str | None = None) -> Any:
    """获取指定日期的龙虎榜数据。

    Param:
        date: 日期，格式 YYYY-MM-DD，默认 None 表示当天
    Return:
        龙虎榜列表数据
    """
    from app.market_data.market.public import get_dragon_tiger_list
    return await get_dragon_tiger_list(date)


async def _get_daily_review(date: str | None = None, force: bool = False) -> Any:
    """生成每日复盘报告并格式化为 Markdown 文本。

    Param:
        date: 日期，格式 YYYY-MM-DD，默认 None 表示当天
        force: 是否强制重新生成（忽略缓存）
    Return:
        格式化为 Markdown 的复盘报告文本
    """
    result = await get_application_tool_handlers().generate_daily_review(date=date, force=force)

    sections = [f"### {result.title}", "", f"**市场概要**：{result.market_summary}", ""]
    for review in [result.index_review, result.hotspot_review, result.dragon_tiger_review]:
        sections.append(f"### {review.title}")
        sections.append(review.summary)
        for bullet in review.bullets:
            sections.append(f"- {bullet}")
        sections.append("")
    if result.risk_alerts:
        sections.append("### ⚠️ 风险提示")
        for alert in result.risk_alerts:
            sections.append(f"- {alert}")
        sections.append("")
    if result.opportunities:
        sections.append("### 💡 机会展望")
        for opp in result.opportunities:
            sections.append(f"- {opp}")
        sections.append("")
    if result.strategy_notes:
        sections.append("### 📋 策略建议")
        for note in result.strategy_notes:
            sections.append(f"- {note}")
        sections.append("")
    if result.llm_review:
        sections.append("### 🤖 AI 深度分析")
        sections.append(result.llm_review)
    return "\n".join(sections)


async def _get_macro_data() -> Any:
    """获取宏观经济指标汇总：CPI、PPI、PMI 和货币供应量。

    Return:
        包含 cpi/ppi/pmi/money_supply 四个板块的字典
    """
    from app.market_data.market.public import get_macro_data
    return await get_macro_data()


def register_market_tools():
    """注册市场相关技能：get_market_overview、get_hot_rank、get_dragon_tiger、get_daily_review、get_macro_data。"""
    registry.register_tool(Tool(
        name="get_market_overview",
        description="获取大盘概览，包括主要指数（上证、深证、创业板等）实时行情和两市成交额。当用户问'大盘怎么样''指数行情''市场情况'时调用。",
        parameters={"type": "object", "properties": {}},
        policy=_MARKET_REALTIME_POLICY,
        executor=_get_market_overview,
    ))

    registry.register_tool(Tool(
        name="get_hot_rank",
        description="获取热门排名数据。当用户问'最近什么火''热门股''热门概念''热门行业'时调用，通过type参数指定查询类型。",
        parameters={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["stocks", "concepts", "industries"],
                    "default": "stocks",
                    "description": "热门类型：stocks=热门股票，concepts=热门概念，industries=热门行业",
                },
            },
        },
        policy=_HOT_RANK_POLICY,
        executor=_get_hot_rank,
    ))

    registry.register_tool(Tool(
        name="get_dragon_tiger",
        description="获取龙虎榜数据，查看游资和机构席位动向。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "日期，格式 YYYY-MM-DD；省略则查询当天",
                },
            },
        },
        policy=_MARKET_DAILY_POLICY,
        executor=_get_dragon_tiger,
    ))

    registry.register_tool(Tool(
        name="get_daily_review",
        description="生成每日大盘复盘报告，包含指数表现、热点题材、龙虎榜、风险提示、机会展望和策略建议。当用户问'今天大盘怎么样''复盘''市场总结'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "日期，格式 YYYY-MM-DD；省略则生成当天复盘",
                },
            },
        },
        policy=_REVIEW_POLICY,
        executor=_get_daily_review,
    ))

    registry.register_tool(Tool(
        name="get_macro_data",
        description="获取最新常用宏观指标汇总，包括CPI、PPI、PMI和货币供应量M0/M1/M2。指定历史区间、口径或单项查询时使用 iwencai_market_macro。",
        parameters={"type": "object", "properties": {}},
        policy=_MACRO_POLICY,
        executor=_get_macro_data,
    ))
