"""产业链免配置公共数据兜底采集。"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.agentic.public import execute_web_search
from app.financial_data.industry.public import call_industry_data
from app.financial_data.market.public import get_market_news
from app.financial_data.stock.public import search_stocks


@dataclass
class IndustryPublicSources:
    stock_search: Callable[..., Awaitable[Any]]
    market_news: Callable[..., Awaitable[Any]]
    web_search: Callable[..., Awaitable[Any]]


public_data = IndustryPublicSources(
    stock_search=search_stocks,
    market_news=get_market_news,
    web_search=execute_web_search,
)
_TOPIC_SUFFIXES = ("产业链", "行业", "板块", "概念", "题材")


def _normalize_topic(value: Any) -> str:
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())
    changed = True
    while changed and text:
        changed = False
        for suffix in _TOPIC_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    return text


def _relevance_score(topic: str, candidate: Any) -> int:
    normalized = _normalize_topic(candidate)
    if not topic or not normalized:
        return 0
    if normalized == topic:
        return 100
    if min(len(topic), len(normalized)) >= 2 and (topic in normalized or normalized in topic):
        return max(60, 90 - abs(len(topic) - len(normalized)))
    return 0


def _as_records(value: Any) -> list[dict]:
    if value is None or isinstance(value, Exception):
        return []
    if hasattr(value, "to_dict") and not isinstance(value, dict):
        try:
            value = value.to_dict(orient="records")
        except TypeError:
            value = value.to_dict()
    if not isinstance(value, list):
        return []
    records = []
    for item in value:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if isinstance(item, dict):
            records.append(dict(item))
    return records


def _web_results(value: Any) -> list[dict]:
    if not isinstance(value, dict):
        return []
    return _as_records(value.get("results"))


def _dedupe_records(values: list[dict]) -> list[dict]:
    records = []
    seen = set()
    for item in values:
        key = str(item.get("url") or item.get("title") or item)
        if key in seen:
            continue
        seen.add(key)
        records.append(item)
    return records


def _ranking_rows(payload: Any, sector_type: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = []
    seen = set()
    for item in [*(payload.get("top") or []), *(payload.get("bottom") or [])]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("industry_name") or "").strip()
        code = str(item.get("code") or item.get("industry_code") or "").strip()
        key = code or name
        if not name or not key or key in seen:
            continue
        seen.add(key)
        rows.append({**item, "name": name, "code": code, "sector_type": sector_type})
    return rows


def _select_relevant_rows(name: str, rows: list[dict], limit: int = 5) -> list[dict]:
    topic = _normalize_topic(name)
    scored = [(_relevance_score(topic, row.get("name")), row) for row in rows]
    scored = [(score, row) for score, row in scored if score > 0]
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    return [row for _, row in scored[:limit]]


def _select_relevant_news(name: str, sectors: list[dict], value: Any, limit: int = 20) -> list[dict]:
    keywords = {
        keyword
        for keyword in [
            _normalize_topic(name),
            *(_normalize_topic(item.get("name")) for item in sectors),
        ]
        if len(keyword) >= 2
    }
    selected = []
    for item in _as_records(value):
        searchable = _normalize_topic(f"{item.get('title', '')}{item.get('content', '')}")
        if searchable and any(keyword in searchable for keyword in keywords):
            selected.append(item)
            if len(selected) >= limit:
                break
    return selected


def _select_relevant_flows(name: str, sectors: list[dict], values: list[Any]) -> list[dict]:
    topic = _normalize_topic(name)
    sector_names = {_normalize_topic(item.get("name")) for item in sectors}
    selected = []
    for value in values:
        for item in _as_records(value):
            item_name = item.get("industry_name") or item.get("name") or item.get("板块名称")
            normalized = _normalize_topic(item_name)
            if normalized in sector_names or _relevance_score(topic, item_name) > 0:
                selected.append(item)
    return selected


def _stock_record(item: dict, sector: str = "") -> dict | None:
    code = str(item.get("code") or item.get("代码") or item.get("股票代码") or "").strip()
    name = str(item.get("name") or item.get("名称") or item.get("股票简称") or "").strip()
    if not code and not name:
        return None
    record = {"code": code, "name": name}
    if sector:
        record["sector"] = sector
    return record


async def _industry_call(operation: str, *args):
    return await call_industry_data(operation, *args)


async def collect_public_industry_data(name: str) -> dict:
    """使用免配置行情与资讯源补充产业链研究材料。"""
    results = await asyncio.gather(
        public_data.stock_search(name),
        _industry_call("industry_rankings", 100),
        _industry_call("concept_rankings", 100),
        _industry_call("industry_fund_flow"),
        _industry_call("concept_fund_flow"),
        public_data.market_news(),
        public_data.web_search(
            f"{name} 产业链 市场规模 增长率", engine="baidu", max_results=8,
            time_range="half_year", language="zh",
        ),
        public_data.web_search(
            f"{name} 产业链 竞争格局 龙头公司", engine="baidu", max_results=8,
            time_range="half_year", language="zh",
        ),
        public_data.web_search(
            f"{name} 产业链 核心技术 商业模式", engine="baidu", max_results=8,
            time_range="half_year", language="zh",
        ),
        public_data.web_search(
            f"{name} 产业链 研报", engine="baidu", max_results=8,
            time_range="half_year", language="zh",
        ),
        public_data.web_search(
            f"{name} 政策 扩产 并购 最新", engine="baidu", max_results=8,
            time_range="half_year", language="zh",
        ),
        return_exceptions=True,
    )
    (
        stock_search, industry_rankings, concept_rankings, industry_flow, concept_flow,
        news, market_web, competition_web, technology_web, reports_web, events_web,
    ) = results
    sector_rows = [
        *_ranking_rows(industry_rankings, "industry"),
        *_ranking_rows(concept_rankings, "concept"),
    ]
    matched_sectors = _select_relevant_rows(name, sector_rows)
    component_sectors = [sector for sector in matched_sectors if sector.get("code")][:3]
    component_results = await asyncio.gather(
        *(_industry_call("industry_components", sector["code"]) for sector in component_sectors),
        return_exceptions=True,
    )

    stocks = []
    seen_stocks = set()
    for item in _as_records(stock_search):
        record = _stock_record(item)
        if record and (record["code"] or record["name"]) not in seen_stocks:
            seen_stocks.add(record["code"] or record["name"])
            stocks.append(record)

    competition_data = []
    for sector, components in zip(component_sectors, component_results):
        sector_stocks = []
        for item in _as_records(components):
            record = _stock_record(item, str(sector.get("name") or ""))
            if record is None:
                continue
            sector_stocks.append(record)
            key = record["code"] or record["name"]
            if key not in seen_stocks:
                seen_stocks.add(key)
                stocks.append(record)
        if sector_stocks:
            competition_data.append(
                {
                    "market": sector.get("name", ""),
                    "summary": "东方财富板块成分股",
                    "companies": sector_stocks,
                }
            )

    relevant_flows = _select_relevant_flows(name, matched_sectors, [industry_flow, concept_flow])
    public_events = _dedupe_records(
        [*_select_relevant_news(name, matched_sectors, news), *_web_results(events_web)]
    )
    return {
        "stocks": stocks,
        "market_data": {
            "matched_sectors": matched_sectors,
            "fund_flow": relevant_flows,
            "web_results": _web_results(market_web),
        },
        "competition_data": [*competition_data, *_web_results(competition_web)],
        "technology_data": _web_results(technology_web),
        "reports": _web_results(reports_web),
        "events": public_events,
        "rankings": matched_sectors,
    }


__all__ = ["collect_public_industry_data"]
