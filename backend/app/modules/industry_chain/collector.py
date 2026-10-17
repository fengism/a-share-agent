"""产业链研究数据采集。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.domain.industry_chain import IndustryChainResearchScope
from app.financial_data.industry.public import (
    query_industry_data,
    search_industry_content,
    select_industry_stocks,
)
from app.modules.industry_chain.public_collector import collect_public_industry_data

logger = logging.getLogger(__name__)


@dataclass
class IndustryResearchSources:
    query: Callable[..., Awaitable[Any]]
    search: Callable[..., Awaitable[Any]]
    select_stock: Callable[..., Awaitable[Any]]


research_data = IndustryResearchSources(
    query=query_industry_data,
    search=search_industry_content,
    select_stock=select_industry_stocks,
)
_DATA_KEYS = (
    "stocks",
    "market_data",
    "competition_data",
    "technology_data",
    "reports",
    "events",
    "rankings",
)


class IndustryChainDataUnavailableError(RuntimeError):
    pass


def _resolved(value):
    return value if not isinstance(value, Exception) else {"error": str(value)}


def _has_content(value: Any) -> bool:
    if value is None or isinstance(value, Exception):
        return False
    if isinstance(value, dict):
        if value.get("error"):
            return False
        return any(_has_content(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_content(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


async def collect_industry_chain_data(
    name: str,
    scope: IndustryChainResearchScope | None = None,
) -> dict:
    """按研究主题并行采集产业链材料，仅对缺失维度调用公共数据兜底。"""
    results = await asyncio.gather(
        research_data.select_stock(f"{name}产业链 上中下游", limit=20),
        research_data.query(f"{name}行业 市场规模 增长率 近三年", limit=15),
        research_data.query(f"{name}行业 全球 中国 市场份额 竞争格局", limit=15),
        research_data.query(f"{name}行业 核心技术 商业模式 产业壁垒", limit=15),
        research_data.search(f"{name}产业链 研报", channel="report", size=10),
        research_data.search(f"{name} 政策 中标 扩产 并购", channel="news", size=10),
        return_exceptions=True,
    )
    collected = {
        "stocks": _resolved(results[0]),
        "market_data": _resolved(results[1]),
        "competition_data": _resolved(results[2]),
        "technology_data": _resolved(results[3]),
        "reports": _resolved(results[4]),
        "events": _resolved(results[5]),
        "rankings": [],
    }
    key_dimensions = {
        "stocks": "stocks",
        "market_data": "market",
        "competition_data": "competition",
        "technology_data": "technology",
        "reports": "reports",
        "events": "events",
        "rankings": "market",
    }
    missing_dimensions = {
        dimension for key, dimension in key_dimensions.items() if not _has_content(collected.get(key))
    }
    if missing_dimensions:
        try:
            fallback = await collect_public_industry_data(
                name,
                scope,
                dimensions=missing_dimensions,
            )
        except Exception as error:
            logger.warning("产业链公共数据兜底失败: name=%s, error=%s", name, error)
            fallback = {}
        for key in _DATA_KEYS:
            if not _has_content(collected.get(key)) and _has_content(fallback.get(key)):
                collected[key] = fallback[key]

    if not any(_has_content(collected[key]) for key in _DATA_KEYS):
        raise IndustryChainDataUnavailableError(f"未获取到“{name}”的产业链数据，请稍后重试或在设置中启用问财数据源")
    return collected
