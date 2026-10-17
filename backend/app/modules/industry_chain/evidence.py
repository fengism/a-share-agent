"""Build and validate the compact evidence catalog stored with industry reports."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

from app.agentic.public import AgentEvidence, agent_evidence_id
from app.modules.industry_chain.evidence_content import extract_evidence_content
from app.modules.industry_chain.evidence_windows import render_industry_evidence_section
from app.modules.industry_chain.models import (
    IndustryChainEvidence,
    IndustryChainEvidenceStats,
    IndustryChainResult,
)
from app.modules.industry_chain.numbers import (
    is_bounded_quantity,
    quantity_tokens,
    scalar_in_display_unit,
    specification_tokens,
)

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_DATE_KEYS = ("published_at", "published_time", "article:published_time", "date")
_PROMPT_TOOL_PRIORITY = {
    "analyze_financials": 0,
    "get_stock_valuation_detail": 1,
    "web_fetch": 0,
    "read_pdf": 0,
    "fetch_urls": 0,
    "iwencai_select_stock": 1,
    "iwencai_query": 1,
    "iwencai_search": 2,
    "web_search": 3,
}
_EVIDENCE_DIMENSION_TERMS = {
    "market": ("市场规模", "增速", "增长率", "cagr", "需求", "供给", "价格"),
    "upstream_operations": ("上游", "原材料", "零部件", "执行器", "电机", "丝杠", "硅料", "原粮", "晶圆"),
    "midstream_operations": ("中游", "整机", "本体", "生产", "制造", "组件", "服务器", "酿造"),
    "downstream_operations": ("下游", "客户", "采购", "终端", "渠道", "动销", "应用", "利用率", "预算"),
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
    if tool_name in {"web_search", "web_fetch", "fetch_urls"}:
        return "web"
    if tool_name == "public_industry_data":
        return "public_market_data"
    return "agent_tool"


def _evidence_dimensions(item: AgentEvidence) -> set[str]:
    text = f"{item.arguments}\n{item.content}".lower()
    return {dimension for dimension, terms in _EVIDENCE_DIMENSION_TERMS.items() if any(term in text for term in terms)}


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
        catalog.append(
            IndustryChainEvidence(
                evidence_id=evidence_id,
                tool_name=item.tool_name,
                provider=_provider(item.tool_name),
                material_type=_material_type(item.tool_name),
                arguments=item.arguments[:2000],
                title=_first_field(value, ("title", "name")),
                source_urls=_source_urls(value),
                published_at=_first_field(value, _DATE_KEYS),
                fetched_at=_first_field(value, ("fetched_at",)),
                truncated=_is_truncated(item.content),
                content_preview=_content_preview(value),
                status="error" if item.is_error else "success",
                error_message=_error_message(item.content) if item.is_error else "",
            )
        )
    return catalog


def compact_industry_evidence(
    evidence: list[AgentEvidence] | tuple[AgentEvidence, ...],
    *,
    max_context_length: int = 36_000,
    max_item_length: int = 6_000,
    priority_ids: set[str] | None = None,
    focus_terms: tuple[str, ...] = (),
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
    unique.sort(
        key=lambda pair: (agent_evidence_id(pair[1]) not in (priority_ids or set()), _selection_priority(*pair))
    )

    dimension_cache: dict[str, set[str]] = {}

    def dimensions(item: AgentEvidence) -> set[str]:
        eid = agent_evidence_id(item)
        if eid in dimension_cache:
            return dimension_cache[eid]
        found = _evidence_dimensions(item)
        # Topic mentions in search arguments do not reserve BODY slots.
        found = {dimension for dimension in found if not dimension.endswith("_operations")}
        if item.tool_name in {"web_fetch", "fetch_urls", "read_pdf"}:
            body_text = "\n".join(
                part.text for part in extract_evidence_content(_decode(item.content)) if part.source_url
            ).lower()
            found.update(
                dimension
                for dimension, terms in _EVIDENCE_DIMENSION_TERMS.items()
                if dimension.endswith("_operations") and any(term in body_text for term in terms)
            )
        dimension_cache[eid] = found
        return found

    available_dimensions = {dimension for _, item in unique for dimension in dimensions(item)}
    coverage_candidates: list[tuple[int, AgentEvidence]] = []
    for dimension in _EVIDENCE_DIMENSION_TERMS:
        if dimension not in available_dimensions:
            continue
        candidate = next(
            (pair for pair in unique if dimension in dimensions(pair[1])),
            None,
        )
        if candidate is not None and candidate not in coverage_candidates:
            coverage_candidates.append(candidate)
    chain_candidates = []
    for dimension in ("downstream_operations", "midstream_operations", "upstream_operations"):
        candidate = next((pair for pair in unique if dimension in dimensions(pair[1])), None)
        if candidate is not None and candidate not in chain_candidates:
            chain_candidates.append(candidate)
    coverage_ids = {agent_evidence_id(item) for _, item in coverage_candidates}
    prioritized = [pair for pair in unique if agent_evidence_id(pair[1]) in (priority_ids or set())]
    coverage_ids.update(agent_evidence_id(item) for _, item in prioritized)
    ordered = [
        *chain_candidates,
        *(pair for pair in prioritized if pair not in chain_candidates),
        *(pair for pair in coverage_candidates if pair not in prioritized and pair not in chain_candidates),
        *(pair for pair in unique if agent_evidence_id(pair[1]) not in coverage_ids),
    ]
    effective_item_length = max_item_length
    if coverage_candidates or prioritized:
        # Avoid 6 long company documents consuming the entire 36k synthesis window.
        # Preserve more source-bound excerpts before allocating long single-tool payloads.
        excerpt_slots = min(12, max(len(coverage_candidates), len(prioritized), len(unique)))
        per_dimension_budget = max_context_length // max(1, excerpt_slots) - 512
        effective_item_length = min(max_item_length, max(128, per_dimension_budget))
    selected: list[AgentEvidence] = []
    sections: list[str] = []
    used = 0
    for _, item in ordered:
        section = render_industry_evidence_section(
            item,
            index=len(sections) + 1,
            item_budget=effective_item_length,
            focus_terms=focus_terms,
        )
        cost = len(section) + (1 if sections else 0)
        if used + cost > max_context_length:
            remaining = max_context_length - used - (1 if sections else 0)
            if remaining >= 256:
                section = render_industry_evidence_section(
                    item,
                    index=len(sections) + 1,
                    item_budget=remaining,
                    focus_terms=focus_terms,
                )
                cost = len(section) + (1 if sections else 0)
                if used + cost > max_context_length:
                    continue
            else:
                continue
        selected.append(item)
        sections.append(section)
        used += cost
    rendered = "\n".join(sections) or "暂无可用工具证据"
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
                str(child_key): bound(child, key=str(child_key), depth=depth + 1) for child_key, child in item.items()
            }
        return item

    return cast(dict[str, Any], bound(value))


def _claim_items(result: IndustryChainResult):
    yield from result.research_theses
    yield from result.relationships
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
        allowed_urls = {url for evidence_id in evidence_ids for url in urls_by_evidence.get(evidence_id, set())}
        if _canonical_url(source_url) not in allowed_urls:
            mismatched.add(source_url)
            setattr(item, field_name, "")
    return mismatched


def _material_type(tool_name: str) -> Literal["discovery", "body", "structured", "unknown"]:
    if tool_name in {"web_search", "iwencai_search", "public_industry_data", "get_stock_documents"}:
        return "discovery"
    if tool_name in {"web_fetch", "fetch_urls", "read_pdf"}:
        return "body"
    if tool_name in {
        "iwencai_query",
        "iwencai_select_stock",
        "analyze_financials",
        "get_stock_info",
        "get_stock_valuation_detail",
        "get_commodity_spot_prices",
        "get_customs_trade_data",
    }:
        return "structured"
    return "unknown"


def validate_claim_support(result: IndustryChainResult, evidence: list[AgentEvidence]) -> None:
    """Check literal quotations against original tool bodies, never assert entailment.

    Search snippets and the mixed public-data bundle are discovery material only.
    A quotation match is not a fact check, nor validation of a model-provided page number.
    """
    from app.modules.industry_chain.models import IndustryChainMetric, IndustryChainThesis

    def content(item: AgentEvidence):
        value = _decode(item.content)
        if item.tool_name == "get_customs_trade_data" and isinstance(value, dict):
            # The static profiles must never be treated as measured trade evidence.
            value = {"data": value.get("recent_12m_macro_trend") or []}
        if item.tool_name == "get_commodity_spot_prices" and isinstance(value, dict):
            allowed = {
                "symbol",
                "contract",
                "quote_kind",
                "source",
                "source_url",
                "unit",
                "latest_price",
                "date",
                "change",
                "change_pct",
                "high",
                "low",
                "open",
                "prev_settle",
                "volume",
                "open_interest",
            }
            value = {
                "data": [
                    {key: val for key, val in row.items() if key in allowed}
                    for row in value.get("items", [])
                    if isinstance(row, dict) and row.get("status") == "available"
                ]
            }
        return extract_evidence_content(value, structured=_material_type(item.tool_name) == "structured")

    by_id = {
        agent_evidence_id(item): content(item)
        for item in evidence
        if not item.is_error and _material_type(item.tool_name) in {"body", "structured"}
    }

    def normalize(text: str) -> str:
        return re.sub(r"\s+", "", text)

    missing = 0
    for claim in _claim_items(result):
        if not hasattr(claim, "citations"):
            continue
        if isinstance(claim, IndustryChainThesis):
            claim.claim_type = "inference"
        if getattr(claim, "claim_type", "fact") in {"inference", "opinion"}:
            claim.evidence_basis = claim.claim_type
        claim.verification_status = "unverified"
        claim.verification_notes = []
        accepted = []
        for citation in claim.citations:
            quote = normalize(citation.quote)
            matches = [
                part
                for part in by_id.get(citation.evidence_id, [])
                if len(quote) >= 12 and quote in normalize(part.text)
            ]
            if citation.evidence_id in claim.evidence_ids and matches:
                urls = {part.source_url for part in matches}
                # A batch-level source URL cannot select a different document's quotation.
                if claim.source_url and claim.source_url not in urls:
                    continue
                source_url = claim.source_url or (next(iter(urls)) if len(urls) == 1 else "")
                accepted.append(citation.model_copy(update={"source_url": source_url}))
        if len(accepted) != len(claim.citations):
            claim.verification_notes.append("部分引用未匹配到原始正文，已移除；搜索摘要不能作为正文核验。")
        claim.citations = accepted
        if accepted:
            claim.verification_status = "quote_matched"
            claim.verification_notes.append("仅核对原文片段；语义支持、统计口径与页码仍需人工复核。")
        else:
            missing += 1
            claim.confidence = "low"
            linked = [
                item
                for item in result.evidence_catalog
                if item.evidence_id in claim.evidence_ids and item.status == "success"
            ]
            if linked and all(item.material_type == "discovery" for item in linked):
                claim.verification_notes.append("仅有检索线索或目录；下一步读取原始公告/报告正文。")
            elif any(item.material_type in {"body", "structured"} for item in linked):
                claim.verification_notes.append(
                    "已有正文/数据但引用未匹配；下一步定位同一文档中的逐字片段，不能改写或拼接。"
                )
            else:
                claim.verification_notes.append("尚无可用来源；下一步取得权威披露与对应统计期。")
            claim.verification_notes.append("缺少可匹配原文，结论待验证。")
        if isinstance(claim, IndustryChainMetric):
            if not all((claim.period, claim.unit, claim.region, claim.statistical_scope)):
                claim.verification_notes.append("指标统计期、单位、地域或统计范围不完整。")
                claim.confidence = "low"
                result.quality_status = "degraded"
            numbers = quantity_tokens(claim.value)
            # Preserve signs and percent/per-mille units, and require a single supporting quotation.
            matches_value = bool(numbers) and any(
                set(numbers) <= set(quantity_tokens(citation.quote))
                and specification_tokens(claim.value) <= specification_tokens(citation.quote)
                for citation in accepted
            )
            numeric = scalar_in_display_unit(claim.numeric_value, claim.unit)
            if claim.numeric_value and (
                numeric is None
                or len(numbers) != 1
                or numeric != numbers[0][0]
                or not matches_value
                or is_bounded_quantity(claim.value)
            ):
                claim.numeric_value = ""
                claim.confidence = "low"
                result.quality_status = "degraded"
                claim.verification_notes.append("结构化数值不匹配指标与引用，或包含多个数值，已移除。")
            if not matches_value:
                result.quality_status = "degraded"
                claim.verification_status = "unverified"
                claim.confidence = "low"
                claim.verification_notes.append("指标数值（含正负号、百分号）未匹配同一引用原文，待验证。")
    if missing:
        result.quality_status = "degraded"
        note = f"{missing} 项结构化判断缺少可匹配原文；引用链接存在不代表结论已核实。"
        if note not in result.warnings:
            result.warnings.append(note)
