"""产业链免配置公共数据兜底采集。"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.agentic.public import execute_web_search
from app.core.cache import reference_cache
from app.core.news import parse_news_time
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    resolve_industry_chain_scope,
)
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


def _filter_news_by_scope(
    values: list[dict],
    scope: IndustryChainResearchScope,
) -> list[dict]:
    if scope.start_date is None or scope.end_date is None:
        return values
    filtered = []
    for item in values:
        published_at = parse_news_time(
            str(item.get("publish_time") or item.get("time") or "")
        )
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


PUBLIC_DIMENSIONS = frozenset({
    "stocks",
    "market",
    "competition",
    "technology",
    "chain",
    "drivers_risks",
    "reports",
    "events",
})
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
        scope.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"industry-chain:public:v2:{_normalize_topic(name)}:{dimension}:{scope_json}"


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

    region, date_range, time_range, language = _scope_search_options(resolved_scope)
    company_terms = (
        "A股 上市公司"
        if resolved_scope.company_scope == "a_share"
        else "全球主要公司 上市公司 非上市公司"
    )

    def web_search(topic: str, *, search_time_range: str | None = None):
        return public_data.web_search(
            f"{name}产业链 {topic} {region} {date_range}",
            engine="bing_cn",
            max_results=8,
            time_range=search_time_range or time_range,
            language=language,
        )

    async def collect_market() -> dict:
        industry_rankings, concept_rankings, industry_flow, concept_flow, market_web = await asyncio.gather(
            _industry_call("industry_rankings", 100),
            _industry_call("concept_rankings", 100),
            _industry_call("industry_fund_flow"),
            _industry_call("concept_fund_flow"),
            web_search("市场规模 复合增长率 CAGR 渗透率", search_time_range="any"),
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
                "web_results": _web_results(market_web),
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
        competition_web = web_search(f"竞争格局 市场份额 CR3 CR5 {company_terms}")
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
                competition_data.append({
                    "market": sector.get("name", ""),
                    "summary": "东方财富板块成分股",
                    "companies": sector_stocks,
                })
        return {
            "competition_data": [*competition_data, *_web_results(competition_search)],
            "_component_stocks": component_stocks,
        }

    async def collect_technology() -> dict:
        value = await web_search("核心技术路线 工艺壁垒 成本下降曲线 商业化成熟度")
        return {"technology_data": _web_results(value)}

    async def collect_chain() -> dict:
        upstream, midstream, downstream = await asyncio.gather(
            web_search("上游核心零部件 原材料 关键设备 国产替代率 供应商", search_time_range="any"),
            web_search("中游生产制造 系统集成 总装 分部毛利率 附加值", search_time_range="any"),
            web_search("下游应用场景 终端客户需求 增速 商业化落地", search_time_range="any"),
            return_exceptions=True,
        )
        return {"chain_data": {
            "upstream": _web_results(upstream),
            "midstream": _web_results(midstream),
            "downstream": _web_results(downstream),
        }}

    async def collect_drivers_risks() -> dict:
        value = await web_search("核心增长驱动力 政策催化 供应瓶颈 关键风险")
        return {"driver_risk_data": _web_results(value)}

    async def collect_reports() -> dict:
        value = await web_search("行业深度研报 白皮书 pdf 证券公司", search_time_range="any")
        return {"reports": _web_results(value)}

    async def collect_events(matched_sectors: list[dict]) -> dict:
        news, events_web = await asyncio.gather(
            public_data.market_news(),
            web_search("重大行业政策 头部企业扩产 订单 并购 最新事件"),
            return_exceptions=True,
        )
        relevant_news = _filter_news_by_scope(
            _select_relevant_news(name, matched_sectors, news),
            resolved_scope,
        )
        return {"events": _dedupe_records([*relevant_news, *_web_results(events_web)])}

    cache_hits: list[str] = []
    cache_misses: list[str] = []
    failed_dimensions: list[str] = []
    dimension_payloads: dict[str, dict] = {}

    async def load_dimension(dimension: str, collector: Callable[[], Awaitable[dict]]) -> dict:
        key = _dimension_cache_key(name, dimension, resolved_scope)
        found, cached = reference_cache.get_with_status(key)
        if found and isinstance(cached, dict):
            cache_hits.append(dimension)
            return cached
        cache_misses.append(dimension)
        payload = await collector()
        reference_cache.set(key, payload, ttl=_DIMENSION_TTL_SECONDS[dimension])
        return payload

    needs_market_context = bool(requested & {"market", "competition", "events"})
    market_payload: dict = {}
    if needs_market_context:
        try:
            market_payload = await load_dimension("market", collect_market)
        except Exception:
            failed_dimensions.append("market")
        else:
            if "market" in requested:
                dimension_payloads["market"] = market_payload
    matched_sectors = list((market_payload.get("market_data") or {}).get("matched_sectors") or [])

    collectors: dict[str, Callable[[], Awaitable[dict]]] = {
        "stocks": collect_stocks,
        "competition": lambda: collect_competition(matched_sectors),
        "technology": collect_technology,
        "chain": collect_chain,
        "drivers_risks": collect_drivers_risks,
        "reports": collect_reports,
        "events": lambda: collect_events(matched_sectors),
    }
    selected = [dimension for dimension in sorted(requested) if dimension != "market"]
    outcomes = await asyncio.gather(
        *(load_dimension(dimension, collectors[dimension]) for dimension in selected),
        return_exceptions=True,
    )
    for dimension, outcome in zip(selected, outcomes):
        if isinstance(outcome, Exception):
            failed_dimensions.append(dimension)
            continue
        dimension_payloads[dimension] = outcome

    combined: dict[str, Any] = {
        "research_scope": resolved_scope.model_dump(mode="json", exclude_none=True),
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
        "cache_hits": sorted(cache_hits),
        "cache_misses": sorted(cache_misses),
        "failed_dimensions": sorted(failed_dimensions),
        "successful_dimensions": sorted(set(dimension_payloads) - set(failed_dimensions)),
    }
    return combined


__all__ = ["PUBLIC_DIMENSIONS", "collect_public_industry_data"]
