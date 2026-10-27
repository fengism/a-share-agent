"""产业链免配置公共数据兜底采集。"""

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.agentic_integration.public import execute_web_search
from app.core.cache import reference_cache
from app.core.news import parse_news_time
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    resolve_industry_chain_scope,
)
from app.financial_data.industry.public import call_industry_data
from app.financial_data.market.public import get_market_news
from app.financial_data.stock.public import search_stocks
from app.modules.industry_chain.query_plan import source_packages

logger = logging.getLogger(__name__)


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


def _filter_news_by_scope(
    values: list[dict],
    scope: IndustryChainResearchScope,
) -> list[dict]:
    if scope.start_date is None or scope.end_date is None:
        return values
    filtered = []
    for item in values:
        published_at = parse_news_time(str(item.get("publish_time") or item.get("time") or ""))
        if published_at.year <= 1:
            continue
        if scope.start_date <= published_at.date() <= scope.end_date:
            filtered.append(item)
    return filtered


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


def _scope_search_options(scope: IndustryChainResearchScope) -> tuple[str, str, str, str]:
    region = {
        "china": "中国",
        "global": "全球",
        "china_and_global": "中国 全球 对比",
    }[scope.region]
    date_range = f"{scope.start_date} 至 {scope.end_date} 基准日 {scope.as_of_date}"
    time_range = "half_year" if scope.time_range == "half_year" else "any"
    language = "zh" if scope.region == "china" else "any"
    return region, date_range, time_range, language


PUBLIC_DIMENSIONS = frozenset(
    {
        "stocks",
        "market",
        "competition",
        "technology",
        "chain",
        "drivers_risks",
        "reports",
        "events",
    }
)
_DIMENSION_TTL_SECONDS = {
    "stocks": 6 * 60 * 60,
    "market": 15 * 60,
    "competition": 6 * 60 * 60,
    "technology": 24 * 60 * 60,
    "chain": 24 * 60 * 60,
    "drivers_risks": 6 * 60 * 60,
    "reports": 24 * 60 * 60,
    "events": 30 * 60,
}


def _dimension_cache_key(
    name: str,
    dimension: str,
    scope: IndustryChainResearchScope,
) -> str:
    scope_json = json.dumps(
        scope.model_dump(mode="json", exclude_none=True, exclude={"refresh_dimensions"}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"industry-chain:public:v4:{_normalize_topic(name)}:{dimension}:{scope_json}"


async def collect_public_industry_data(
    name: str,
    scope: IndustryChainResearchScope | None = None,
    dimensions: set[str] | None = None,
) -> dict:
    """按维度采集并缓存免配置行情与资讯，只刷新缺失或已过期的部分。"""
    resolved_scope = resolve_industry_chain_scope(scope)
    requested = set(dimensions) if dimensions is not None else set(PUBLIC_DIMENSIONS)
    unknown = requested - PUBLIC_DIMENSIONS
    if unknown:
        raise ValueError(f"未知产业链公共数据维度: {', '.join(sorted(unknown))}")

    _, _, time_range, language = _scope_search_options(resolved_scope)
    packages = {package.key: package for package in source_packages(name, resolved_scope)}
    # One request-local task per document family; no per-metric fan-out and no cross-user cache.
    searches: dict[str, asyncio.Task] = {}

    async def source_search(family: str):
        if family not in searches:
            query = f"{name} 政策公告 {resolved_scope.end_date.year}" if family == "events" else packages[family].query
            searches[family] = asyncio.create_task(
                public_data.web_search(
                    query,
                    max_results=8,
                    time_range=time_range if family == "events" else "any",
                    language=language,
                )
            )
        return await searches[family]

    def candidates(value, family):
        return [{**row, "discovery_group": family, "content_status": "not_fetched"} for row in _web_results(value)]

    async def collect_market() -> dict:
        industry_rankings, concept_rankings, industry_flow, concept_flow, market_web = await asyncio.gather(
            _industry_call("industry_rankings", 100),
            _industry_call("concept_rankings", 100),
            _industry_call("industry_fund_flow"),
            _industry_call("concept_fund_flow"),
            source_search("landscape"),
            return_exceptions=True,
        )
        sector_rows = [
            *_ranking_rows(industry_rankings, "industry"),
            *_ranking_rows(concept_rankings, "concept"),
        ]
        matched_sectors = _select_relevant_rows(name, sector_rows)
        return {
            "market_data": {
                "matched_sectors": matched_sectors,
                "fund_flow": _select_relevant_flows(
                    name,
                    matched_sectors,
                    [industry_flow, concept_flow],
                ),
                "web_results": candidates(market_web, "landscape"),
            },
            "rankings": matched_sectors,
        }

    async def collect_stocks() -> dict:
        if resolved_scope.company_scope != "a_share":
            return {"stocks": []}
        value = await public_data.stock_search(f"{name}产业链 A股 上中下游")
        stocks = []
        seen = set()
        for item in _as_records(value):
            record = _stock_record(item)
            if record is None:
                continue
            key = record["code"] or record["name"]
            if key in seen:
                continue
            seen.add(key)
            stocks.append(record)
        return {"stocks": stocks}

    async def collect_competition(matched_sectors: list[dict]) -> dict:
        competition_web = source_search("landscape")
        component_sectors = [sector for sector in matched_sectors if sector.get("code")][:3]
        component_results = await asyncio.gather(
            *(_industry_call("industry_components", sector["code"]) for sector in component_sectors),
            return_exceptions=True,
        )
        competition_search = await competition_web
        competition_data = []
        component_stocks = []
        for sector, components in zip(component_sectors, component_results):
            sector_stocks = []
            for item in _as_records(components):
                record = _stock_record(item, str(sector.get("name") or ""))
                if record is not None:
                    sector_stocks.append(record)
                    component_stocks.append(record)
            if sector_stocks:
                competition_data.append(
                    {
                        "market": sector.get("name", ""),
                        "summary": "东方财富板块成分股",
                        "companies": sector_stocks,
                    }
                )
        return {
            "competition_data": [*competition_data, *candidates(competition_search, "landscape")],
            "_component_stocks": component_stocks,
        }

    async def collect_technology() -> dict:
        return {"technology_data": candidates(await source_search("landscape"), "landscape")}

    async def collect_chain() -> dict:
        # Broad document discovery cannot establish tier-specific facts or companies.
        return {
            "chain_data": {
                "upstream": [],
                "midstream": [],
                "downstream": [],
                "source_candidates": candidates(await source_search("landscape"), "landscape"),
            }
        }

    async def collect_drivers_risks() -> dict:
        return {"driver_risk_data": candidates(await source_search("demand"), "demand")}

    async def collect_reports() -> dict:
        return {"reports": candidates(await source_search("landscape"), "landscape")}

    async def collect_events(matched_sectors: list[dict]) -> dict:
        news, events_web = await asyncio.gather(
            public_data.market_news(),
            source_search("events"),
            return_exceptions=True,
        )
        relevant_news = _filter_news_by_scope(
            _select_relevant_news(name, matched_sectors, news),
            resolved_scope,
        )
        return {"events": _dedupe_records([*relevant_news, *candidates(events_web, "events")])}

    cache_hits: list[str] = []
    cache_misses: list[str] = []
    failed_dimensions: list[str] = []
    dimension_payloads: dict[str, dict] = {}

    async def load_dimension(dimension: str, collector: Callable[[], Awaitable[dict]]) -> dict:
        key = _dimension_cache_key(name, dimension, resolved_scope)
        found, cached = reference_cache.get_with_status(key)
        if found and isinstance(cached, dict) and dimension not in resolved_scope.refresh_dimensions:
            cache_hits.append(dimension)
            return cached
        cache_misses.append(dimension)
        try:
            payload = await asyncio.wait_for(collector(), timeout=25.0)
        except asyncio.TimeoutError:
            logger.warning("公共数据维度采集超时: name=%s, dimension=%s", name, dimension)
            failed_dimensions.append(dimension)
            return {"error": f"维度 {dimension} 采集超时"}
        except Exception as exc:
            logger.warning("公共数据维度采集异常: name=%s, dimension=%s, error=%s", name, dimension, exc)
            failed_dimensions.append(dimension)
            return {"error": str(exc)}

        # Empty/error-only payloads must not poison a dimension cache.
        def has_content(value):
            if isinstance(value, dict):
                return not value.get("error") and any(has_content(v) for k, v in value.items() if not k.startswith("_"))
            if isinstance(value, list):
                return any(has_content(v) for v in value)
            return bool(value)

        if has_content(payload):
            reference_cache.set(key, payload, ttl=_DIMENSION_TTL_SECONDS[dimension])
        else:
            failed_dimensions.append(dimension)
        return payload

    needs_market_context = bool(requested & {"market", "competition", "events"})
    independent_dimensions = [
        dim for dim in sorted(requested) if dim in {"stocks", "technology", "chain", "drivers_risks", "reports"}
    ]

    independent_collectors: dict[str, Callable[[], Awaitable[dict]]] = {
        "stocks": collect_stocks,
        "technology": collect_technology,
        "chain": collect_chain,
        "drivers_risks": collect_drivers_risks,
        "reports": collect_reports,
    }

    # 阶段一：解耦并行——同时并发执行所有独立维度与 market 维度
    first_wave_tasks: list[tuple[str, Awaitable[dict]]] = [
        (dim, load_dimension(dim, independent_collectors[dim])) for dim in independent_dimensions
    ]
    if needs_market_context:
        first_wave_tasks.append(("market", load_dimension("market", collect_market)))

    market_payload: dict = {}
    if first_wave_tasks:
        first_wave_outcomes = await asyncio.gather(
            *(task for _, task in first_wave_tasks),
            return_exceptions=True,
        )
        for (dim, _), outcome in zip(first_wave_tasks, first_wave_outcomes):
            if isinstance(outcome, Exception):
                failed_dimensions.append(dim)
                continue
            if dim == "market":
                market_payload = outcome
                if "market" in requested:
                    dimension_payloads["market"] = outcome
            else:
                dimension_payloads[dim] = outcome

    matched_sectors = list((market_payload.get("market_data") or {}).get("matched_sectors") or [])

    # 阶段二：并行采集依赖 matched_sectors 的维度（competition, events）
    dependent_dimensions = [dim for dim in sorted(requested) if dim in {"competition", "events"}]
    if dependent_dimensions:
        dependent_collectors: dict[str, Callable[[], Awaitable[dict]]] = {
            "competition": lambda: collect_competition(matched_sectors),
            "events": lambda: collect_events(matched_sectors),
        }
        dependent_outcomes = await asyncio.gather(
            *(load_dimension(dim, dependent_collectors[dim]) for dim in dependent_dimensions),
            return_exceptions=True,
        )
        for dim, outcome in zip(dependent_dimensions, dependent_outcomes):
            if isinstance(outcome, Exception):
                failed_dimensions.append(dim)
                continue
            dimension_payloads[dim] = outcome

    combined: dict[str, Any] = {
        "research_scope": resolved_scope.model_dump(mode="json", exclude_none=True, exclude={"refresh_dimensions"}),
    }
    component_stocks: list[dict] = []
    for payload in dimension_payloads.values():
        component_stocks.extend(payload.get("_component_stocks") or [])
        combined.update({key: value for key, value in payload.items() if not key.startswith("_")})

    stocks = [*(combined.get("stocks") or []), *component_stocks]
    if stocks:
        deduped_stocks = []
        seen_stocks = set()
        for stock in stocks:
            key = stock.get("code") or stock.get("name")
            if not key or key in seen_stocks:
                continue
            seen_stocks.add(key)
            deduped_stocks.append(stock)
        combined["stocks"] = deduped_stocks

    combined["_collection_metadata"] = {
        "requested_dimensions": sorted(requested),
        "refresh_dimensions": sorted(set(resolved_scope.refresh_dimensions)),
        "cache_hits": sorted(cache_hits),
        "cache_misses": sorted(cache_misses),
        "failed_dimensions": sorted(failed_dimensions),
        "successful_dimensions": sorted(set(dimension_payloads) - set(failed_dimensions)),
    }
    return combined


__all__ = ["PUBLIC_DIMENSIONS", "collect_public_industry_data"]
