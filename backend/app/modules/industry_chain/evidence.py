"""Build and validate the compact evidence catalog stored with industry reports."""

from __future__ import annotations

import json
import re
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

from app.agentic.contracts import render_agent_evidence
from app.agentic.public import AgentEvidence, agent_evidence_id
from app.modules.industry_chain.models import (
    IndustryChainEvidence,
    IndustryChainEvidenceStats,
    IndustryChainResult,
)

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_DATE_KEYS = ("published_at", "published_time", "article:published_time", "date")
_PROMPT_TOOL_PRIORITY = {
    "fetch_url": 0,
    "fetch_urls": 0,
    "iwencai_select_stock": 1,
    "iwencai_query": 1,
    "iwencai_search": 2,
    "web_search": 3,
}
_EVIDENCE_DIMENSION_TERMS = {
    "market": ("市场规模", "增速", "增长率", "cagr", "需求", "供给", "价格"),
    "chain": ("产业链", "上游", "中游", "下游", "原材料", "制造", "应用"),
    "competition": ("竞争格局", "市场份额", "份额", "集中度", "龙头", "公司", "厂商"),
    "technology": ("技术路线", "技术", "工艺", "量产", "性能", "迭代"),
    "events": ("政策", "事件", "公告", "扩产", "并购", "投资", "资本", "订单"),
    "risks_drivers": ("风险", "驱动", "催化", "约束", "波动"),
}


def _decode(content: str) -> Any:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return content
    if isinstance(payload, dict) and payload.get("ok") is True and "data" in payload:
        return payload["data"]
    return payload


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _first_field(value: Any, keys: tuple[str, ...]) -> str:
    for item in _walk(value):
        if not isinstance(item, dict):
            continue
        for key in keys:
            candidate = item.get(key)
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()
    return ""


def _source_urls(value: Any) -> list[str]:
    urls: list[str] = []
    for item in _walk(value):
        if isinstance(item, str):
            for url in _URL_PATTERN.findall(item):
                cleaned = url.rstrip(".,;，。；)]}")
                if cleaned not in urls:
                    urls.append(cleaned)
                    if len(urls) >= 8:
                        return urls
    return urls


def _content_preview(value: Any) -> str:
    content = _first_field(value, ("content", "summary", "snippet", "description"))
    if not content:
        content = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    return re.sub(r"\s+", " ", content).strip()[:500]


def _is_truncated(content: str) -> bool:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return any(isinstance(item, dict) and item.get("truncated") is True for item in _walk(payload))


def _error_message(content: str) -> str:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return content.strip()[:500]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "").strip()[:500]
        if error:
            return str(error).strip()[:500]
    return ""


def _provider(tool_name: str) -> str:
    if tool_name.startswith("iwencai"):
        return "iwencai"
    if tool_name in {"web_search", "fetch_url", "fetch_urls"}:
        return "web"
    if tool_name == "public_industry_data":
        return "public_market_data"
    return "agent_tool"


def _evidence_dimensions(item: AgentEvidence) -> set[str]:
    text = f"{item.arguments}\n{item.content}".lower()
    return {
        dimension
        for dimension, terms in _EVIDENCE_DIMENSION_TERMS.items()
        if any(term in text for term in terms)
    }


def _selection_priority(index: int, item: AgentEvidence) -> tuple[int, int]:
    return _PROMPT_TOOL_PRIORITY.get(item.tool_name, 4), index


def build_evidence_catalog(evidence: list[AgentEvidence] | tuple[AgentEvidence, ...]) -> list[IndustryChainEvidence]:
    catalog: list[IndustryChainEvidence] = []
    seen: set[str] = set()
    for item in evidence:
        evidence_id = agent_evidence_id(item)
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        value = _decode(item.content)
        catalog.append(IndustryChainEvidence(
            evidence_id=evidence_id,
            tool_name=item.tool_name,
            provider=_provider(item.tool_name),
            arguments=item.arguments[:2000],
            title=_first_field(value, ("title", "name")),
            source_urls=_source_urls(value),
            published_at=_first_field(value, _DATE_KEYS),
            fetched_at=_first_field(value, ("fetched_at",)),
            truncated=_is_truncated(item.content),
            content_preview=_content_preview(value),
            status="error" if item.is_error else "success",
            error_message=_error_message(item.content) if item.is_error else "",
        ))
    return catalog


def compact_industry_evidence(
    evidence: list[AgentEvidence] | tuple[AgentEvidence, ...],
    *,
    max_context_length: int = 36_000,
    max_item_length: int = 6_000,
) -> tuple[tuple[AgentEvidence, ...], str, IndustryChainEvidenceStats]:
    unique: list[tuple[int, AgentEvidence]] = []
    seen: set[str] = set()
    failed_count = 0
    for index, item in enumerate(evidence):
        evidence_id = agent_evidence_id(item)
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        if item.is_error:
            failed_count += 1
            continue
        unique.append((index, item))
    unique.sort(key=lambda pair: _selection_priority(*pair))

    available_dimensions = {
        dimension
        for _, item in unique
        for dimension in _evidence_dimensions(item)
    }
    coverage_candidates: list[tuple[int, AgentEvidence]] = []
    for dimension in _EVIDENCE_DIMENSION_TERMS:
        if dimension not in available_dimensions:
            continue
        candidate = next(
            (pair for pair in unique if dimension in _evidence_dimensions(pair[1])),
            None,
        )
        if candidate is not None and candidate not in coverage_candidates:
            coverage_candidates.append(candidate)
    coverage_ids = {agent_evidence_id(item) for _, item in coverage_candidates}
    ordered = [
        *coverage_candidates,
        *(pair for pair in unique if agent_evidence_id(pair[1]) not in coverage_ids),
    ]
    effective_item_length = max_item_length
    if coverage_candidates:
        per_dimension_budget = max_context_length // len(coverage_candidates) - 512
        effective_item_length = min(max_item_length, max(128, per_dimension_budget))
    selected: list[AgentEvidence] = []
    rendered = "暂无可用工具证据"
    for _, item in ordered:
        candidate = render_agent_evidence(
            [*selected, item],
            max_context_length=max_context_length,
            max_item_length=effective_item_length,
        )
        if agent_evidence_id(item) not in candidate:
            continue
        selected.append(item)
        rendered = candidate
    stats = IndustryChainEvidenceStats(
        total_count=len(evidence),
        unique_count=len(seen),
        selected_count=len(selected),
        omitted_count=max(0, len(evidence) - len(selected)),
        failed_count=failed_count,
        prompt_characters=len(rendered),
    )
    return tuple(selected), rendered, stats


def compact_public_industry_data(value: dict[str, Any]) -> dict[str, Any]:
    top_level_limits = {
        "stocks": 20,
        "market_data": 12,
        "competition_data": 12,
        "technology_data": 12,
        "chain_data": 12,
        "driver_risk_data": 12,
        "reports": 12,
        "events": 12,
        "rankings": 8,
    }

    def bound(item: Any, *, key: str = "", depth: int = 0) -> Any:
        if depth >= 6:
            return str(item)[:2_000]
        if isinstance(item, str):
            return item[:2_000]
        if isinstance(item, list):
            limit = top_level_limits.get(key, 12)
            return [bound(child, depth=depth + 1) for child in item[:limit]]
        if isinstance(item, dict):
            return {
                str(child_key): bound(child, key=str(child_key), depth=depth + 1)
                for child_key, child in item.items()
            }
        return item

    return cast(dict[str, Any], bound(value))


def _claim_items(result: IndustryChainResult):
    yield from result.market_metrics
    yield from result.technology_routes
    yield from result.upstream
    yield from result.midstream
    yield from result.downstream
    yield from result.trends
    yield from result.driver_insights
    yield from result.risk_insights
    yield from result.capital_moves
    yield from result.key_events
    yield from result.key_stocks
    yield from result.sources
    yield from result.conflicts
    for group in result.competition:
        yield from group.companies


def validate_result_evidence_ids(
    result: IndustryChainResult,
    catalog: list[IndustryChainEvidence],
) -> set[str]:
    valid_ids = {item.evidence_id for item in catalog if item.status == "success"}
    unknown: set[str] = set()
    for field_name in ("summary_evidence_ids", "positioning_evidence_ids"):
        summary_accepted: list[str] = []
        for evidence_id in getattr(result, field_name):
            if evidence_id in valid_ids:
                if evidence_id not in summary_accepted:
                    summary_accepted.append(evidence_id)
            else:
                unknown.add(evidence_id)
        setattr(result, field_name, summary_accepted)
    for item in _claim_items(result):
        claim_accepted: list[str] = []
        for evidence_id in item.evidence_ids:
            if evidence_id in valid_ids:
                if evidence_id not in claim_accepted:
                    claim_accepted.append(evidence_id)
            else:
                unknown.add(evidence_id)
        item.evidence_ids = claim_accepted
    return unknown


def _canonical_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def validate_result_source_urls(
    result: IndustryChainResult,
    catalog: list[IndustryChainEvidence],
) -> set[str]:
    urls_by_evidence = {
        item.evidence_id: {_canonical_url(url) for url in item.source_urls if _canonical_url(url)}
        for item in catalog
        if item.status == "success"
    }
    mismatched: set[str] = set()
    for item in _claim_items(result):
        field_name = "url" if hasattr(item, "url") and not hasattr(item, "source_url") else "source_url"
        source_url = str(getattr(item, field_name, "") or "").strip()
        evidence_ids = getattr(item, "evidence_ids", [])
        if not source_url or not evidence_ids:
            continue
        allowed_urls = {
            url
            for evidence_id in evidence_ids
            for url in urls_by_evidence.get(evidence_id, set())
        }
        if _canonical_url(source_url) not in allowed_urls:
            mismatched.add(source_url)
            setattr(item, field_name, "")
    return mismatched
