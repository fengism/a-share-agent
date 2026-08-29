from __future__ import annotations

import asyncio
from typing import Any

from app.agentic.catalog import registry
from app.agentic.tools.application import get_application_tool_handlers
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.agentic.tools.packs.stock import helpers
from app.agentic.tools.packs.stock.financial_analysis import analyze_financials as _analyze_financials

_HIGH_REALTIME_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=60,
    freshness="near_realtime",
    timeout_seconds=30,
    max_parallel_calls=2,
)
_HIGH_DAILY_POLICY = ToolPolicy(cost="high", cache_ttl_seconds=900, freshness="daily")
_ANALYZE_SECTION_TIMEOUTS = {
    "info": 8.0,
    "valuation": 15.0,
    "technical": 15.0,
    "news": 12.0,
    "sentiment": 12.0,
}

_RESEARCH_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=60,
    freshness="near_realtime",
    timeout_seconds=180,
    max_parallel_calls=2,
)


async def _gather_labeled(
    tasks: dict[str, Any],
    timeout_seconds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run labeled sections concurrently with independent timeout/error degradation."""
    section_timeouts = timeout_seconds or {}

    async def run_section(label: str, awaitable: Any) -> Any:
        try:
            timeout = section_timeouts.get(label)
            if timeout is None:
                return await awaitable
            async with asyncio.timeout(timeout):
                return await awaitable
        except TimeoutError:
            return {"status": "timeout", "error": f"{label} 加载超时"}
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return {
                "status": "failed",
                "error": str(error) or type(error).__name__,
            }

    labels = list(tasks)
    results = await asyncio.gather(
        *(run_section(label, tasks[label]) for label in labels)
    )
    return dict(zip(labels, results, strict=True))


async def _analyze_stock(code: str) -> Any:
    """组合技能：一键获取个股全维度数据（信息+估值+技术+新闻+情绪）。"""
    sections = await _gather_labeled(
        {
            "info": helpers.get_stock_info(code),
            "valuation": helpers.get_stock_valuation_detail(code),
            "technical": helpers.get_stock_technical_indicators(code),
            "news": helpers.get_stock_news(code),
            "sentiment": helpers.get_stock_sentiment(code),
        },
        _ANALYZE_SECTION_TIMEOUTS,
    )
    unavailable_sections = [
        label
        for label, result in sections.items()
        if isinstance(result, dict) and result.get("error")
    ]
    return {
        "code": code,
        "partial": bool(unavailable_sections),
        "unavailable_sections": unavailable_sections,
        **sections,
    }


async def _sector_analysis(name: str) -> Any:
    """组合技能：复用产业链 Agent 完成行业研究。"""
    research = await get_application_tool_handlers().research_industry_chain(name)
    return {"industry": name, **research.as_tool_payload()}


async def _get_hot_rank(type: str = "industries") -> Any:
    """获取热门排名数据，根据 type 返回热门概念/行业/股票。

    Param:
        type: 热门类型，concepts=热门概念，industries=热门行业，其他=热门股票
    Return:
        对应类型的热门排名数据
    """
    return await get_application_tool_handlers().get_hot_rank(type=type)


async def _compare_stocks(codes: list[str] | str) -> Any:
    """组合技能：多股对比分析。"""
    return await get_application_tool_handlers().compare_stocks(codes)


def register_composite_tools():
    """注册组合技能：analyze_stock、sector_analysis、compare_stocks、analyze_financials。"""
    registry.register_tool(Tool(
        name="analyze_stock",
        description="一键获取个股全维度分析数据，包括基本信息、详细估值、技术指标、新闻和情绪。当用户要求'分析某只股票''深度分析''全面评估'时调用，比分别调用多个工具更高效。",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "pattern": r"^\d{6}$",
                    "description": "6位股票代码，如 600519",
                },
            },
            "required": ["code"],
        },
        policy=_HIGH_REALTIME_POLICY,
        executor=_analyze_stock,
    ))

    registry.register_tool(Tool(
        name="analyze_financials",
        description="一键获取个股完整财报数据，包括资产负债表、利润表、现金流量表（最近4期）、关键指标，以及分产品/业务/地区的营收与毛利构成。当用户要求财报、财务、主营构成、产品构成、地区构成或毛利分析时调用。",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "pattern": r"^\d{6}$",
                    "description": "6位股票代码，如 600519",
                },
            },
            "required": ["code"],
        },
        policy=_HIGH_DAILY_POLICY,
        executor=_analyze_financials,
    ))

    registry.register_tool(Tool(
        name="sector_analysis",
        description="行业与产业链综合分析，自动汇总板块、成分股、资金流、公开研报和事件资料。当用户问'XX行业怎么样''分析XX产业链'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 50,
                    "description": "行业或产业链名称，如'白酒''半导体''AI服务器产业链'",
                },
            },
            "required": ["name"],
        },
        policy=_RESEARCH_POLICY,
        executor=_sector_analysis,
    ))

    registry.register_tool(Tool(
        name="compare_stocks",
        description="多股对比分析，同时获取多只股票的基本信息和估值数据进行横向对比。最多支持5只股票。当用户问'XX和YY哪个好''对比几只股票'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "codes": {
                    "type": "array",
                    "items": {"type": "string", "pattern": r"^\d{6}$"},
                    "minItems": 2,
                    "maxItems": 5,
                    "uniqueItems": True,
                    "description": "需要对比的2至5个股票代码，如 [\"600519\", \"000858\"]",
                },
            },
            "required": ["codes"],
        },
        policy=_HIGH_REALTIME_POLICY,
        executor=_compare_stocks,
    ))
