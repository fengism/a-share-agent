from __future__ import annotations

import asyncio
from typing import Any

from app.services.chat.tools import stock_helpers as helpers
from app.services.chat.tools.registry import Tool, registry


async def _gather_labeled(tasks: dict[str, Any]) -> dict[str, Any]:
    """并行执行一组带标签的协程任务，异常转为 error 字符串。

    Param:
        tasks: 任务名到协程的映射字典
    Return:
        任务名到结果的字典，异常任务的结果为 {"error": str(exc)}
    """
    labels = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {
        label: {"error": str(result)} if isinstance(result, Exception) else result
        for label, result in zip(labels, results)
    }


async def _analyze_stock(code: str) -> Any:
    """组合技能：一键获取个股全维度数据（信息+估值+技术+新闻+情绪）。"""
    return {
        "code": code,
        **await _gather_labeled({
            "info": helpers.get_stock_info(code),
            "valuation": helpers.get_stock_valuation_detail(code),
            "technical": helpers.get_stock_technical_indicators(code),
            "news": helpers.get_stock_news(code),
            "sentiment": helpers.get_stock_sentiment(code),
        }),
    }


async def _sector_analysis(name: str) -> Any:
    """组合技能：行业分析（热门排名+行业筛选+相关研报）。"""
    return {
        "industry": name,
        **await _gather_labeled({
            "hot_industries": _get_hot_rank("industries"),
            "stocks": helpers.screen_stocks(industries=[name], page=1, page_size=15),
            "reports": helpers.iwencai_search(f"{name} 行业 研报", "report", 10),
        }),
    }


async def _get_hot_rank(type: str = "industries") -> Any:
    """获取热门排名数据，根据 type 返回热门概念/行业/股票。

    Param:
        type: 热门类型，concepts=热门概念，industries=热门行业，其他=热门股票
    Return:
        对应类型的热门排名数据
    """
    from app.services.market.hot_rank import get_hot_stocks, get_ths_hot_concept, get_ths_hot_industry
    if type == "concepts":
        return await get_ths_hot_concept()
    if type == "industries":
        return await get_ths_hot_industry()
    return await get_hot_stocks()


async def _compare_stocks(codes: str) -> Any:
    """组合技能：多股对比分析。codes 为逗号分隔的股票代码。"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) > 5:
        return {"error": "最多对比5只股票"}
    if not code_list:
        return {"error": "请输入至少一个股票代码"}

    async def fetch_one(code: str) -> dict:
        info, valuation = await asyncio.gather(
            helpers.get_stock_info(code),
            helpers.get_stock_valuation_detail(code),
            return_exceptions=True,
        )
        result = {"code": code}
        result["info"] = {"error": str(info)} if isinstance(info, Exception) else info
        result["valuation"] = (
            {"error": str(valuation)} if isinstance(valuation, Exception) else valuation
        )
        return result

    results = await asyncio.gather(*[fetch_one(c) for c in code_list])
    return {"comparison": results}


def register_composite_tools():
    """注册组合技能：analyze_stock、sector_analysis、compare_stocks。"""
    registry.register_tool(Tool(
        name="analyze_stock",
        description="一键获取个股全维度分析数据，包括基本信息、详细估值、技术指标、新闻和情绪。当用户要求'分析某只股票''深度分析''全面评估'时调用，比分别调用多个工具更高效。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 600519"},
            },
            "required": ["code"],
        },
        executor=_analyze_stock,
    ))

    registry.register_tool(Tool(
        name="sector_analysis",
        description="行业综合分析，包括行业热度排名、行业内股票筛选和相关研报。当用户问'XX行业怎么样''分析XX行业'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "行业名称，如'白酒''半导体''新能源'"},
            },
            "required": ["name"],
        },
        executor=_sector_analysis,
    ))

    registry.register_tool(Tool(
        name="compare_stocks",
        description="多股对比分析，同时获取多只股票的基本信息和估值数据进行横向对比。最多支持5只股票。当用户问'XX和YY哪个好''对比几只股票'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "codes": {"type": "string", "description": "逗号分隔的股票代码，如'600519,000858'"},
            },
            "required": ["codes"],
        },
        executor=_compare_stocks,
    ))
