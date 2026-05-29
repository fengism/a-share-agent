from __future__ import annotations

import asyncio
from typing import Any

from app.services.chat.skills.registry import Skill, registry


async def _get_market_overview() -> Any:
    from app.services.market.indices import get_indices
    from app.services.market.volume import get_market_volume
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
    from app.services.market.hot_rank import get_hot_stocks, get_ths_hot_concept, get_ths_hot_industry
    if type == "concepts":
        return await get_ths_hot_concept()
    if type == "industries":
        return await get_ths_hot_industry()
    return await get_hot_stocks()


async def _get_dragon_tiger(date: str | None = None) -> Any:
    from app.services.market.dragon_tiger import get_dragon_tiger_list
    return await get_dragon_tiger_list(date)


async def _get_daily_review(date: str | None = None, force: bool = False) -> Any:
    from app.models.daily_review import DailyReviewRequest
    from app.services.daily_review.pipeline import generate_daily_review
    request = DailyReviewRequest(date=date or None, force=force)
    result = await generate_daily_review(request)

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


def register_market_skills():
    registry.register(Skill(
        name="get_market_overview",
        description="获取大盘概览，包括主要指数（上证、深证、创业板等）实时行情和两市成交额。当用户问'大盘怎么样''指数行情''市场情况'时调用。",
        parameters={"type": "object", "properties": {}},
        executor=_get_market_overview,
    ))

    registry.register(Skill(
        name="get_hot_rank",
        description="获取热门排名数据。当用户问'最近什么火''热门股''热门概念''热门行业'时调用，通过type参数指定查询类型。",
        parameters={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["stocks", "concepts", "industries"],
                    "description": "热门类型：stocks=热门股票，concepts=热门概念，industries=热门行业",
                },
            },
        },
        executor=_get_hot_rank,
    ))

    registry.register(Skill(
        name="get_dragon_tiger",
        description="获取龙虎榜数据，查看游资和机构席位动向。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "日期，格式 YYYY-MM-DD，默认当天",
                },
            },
        },
        executor=_get_dragon_tiger,
    ))

    registry.register(Skill(
        name="get_daily_review",
        description="生成每日大盘复盘报告，包含指数表现、热点题材、龙虎榜、风险提示、机会展望和策略建议。当用户问'今天大盘怎么样''复盘''市场总结'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "日期，格式 YYYY-MM-DD，默认当天",
                },
                "force": {
                    "type": "boolean",
                    "description": "是否强制重新生成（忽略缓存），默认false",
                },
            },
        },
        executor=_get_daily_review,
    ))
