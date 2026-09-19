"""从结构化报告生成确定性的主题口径与研究优先级。"""

from typing import Any

from app.modules.industry_chain.atlas.loader import list_atlas_chains
from app.modules.industry_chain.models import (
    IndustryChainOpportunity,
    IndustryChainResult,
    IndustryChainTopicResolution,
)
from app.modules.industry_chain.public_collector import _normalize_topic


def _unique(values: list[str], *, limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        key = _normalize_topic(clean)
        if not clean or not key or key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if limit is not None and len(result) >= limit:
            break
    return result


def build_topic_resolution(
    requested_name: str,
    result: IndustryChainResult,
    public_data: dict[str, Any],
) -> IndustryChainTopicResolution:
    matched_sectors = [
        str(item.get("name") or "").strip()
        for item in ((public_data.get("market_data") or {}).get("matched_sectors") or [])
        if isinstance(item, dict)
    ]
    topic = _normalize_topic(requested_name)
    atlas_matches: list[str] = []
    for chain in list_atlas_chains():
        candidates = [chain.name, *(chain.aliases or [])]
        if any(
            topic and (
                topic == _normalize_topic(candidate)
                or topic in _normalize_topic(candidate)
                or _normalize_topic(candidate) in topic
            )
            for candidate in candidates
        ):
            atlas_matches.append(chain.name)

    possible_topics = _unique([*matched_sectors, *atlas_matches], limit=6)
    normalized_name = result.name.strip() or requested_name.strip()
    aliases = _unique([*(result.aliases or []), *matched_sectors], limit=10)
    if len(possible_topics) > 1:
        boundary_note = "公开板块与知识库存在多个相近口径，报告已按研究范围综合分析；请结合候选主题确认边界。"
    elif possible_topics:
        boundary_note = f"报告以“{normalized_name}”为主题，并参考“{possible_topics[0]}”板块口径。"
    else:
        boundary_note = f"报告以“{normalized_name}”为主题，未发现可直接映射的标准板块。"
    return IndustryChainTopicResolution(
        requested_name=requested_name.strip(),
        normalized_name=normalized_name,
        aliases=aliases,
        matched_sectors=_unique(matched_sectors, limit=6),
        possible_topics=possible_topics,
        boundary_note=boundary_note,
    )


def build_opportunities(result: IndustryChainResult) -> list[IndustryChainOpportunity]:
    """按证据完整度、景气、催化与风险生成稳定的研究优先级，不作收益预测。"""
    opportunities: list[IndustryChainOpportunity] = []
    seen: set[str] = set()
    risk_items = result.risk_insights or result.risks
    catalyst_items = [*(result.key_events or []), *(result.capital_moves or [])]
    prosperity_base = min(20, 8 + 2 * len(result.driver_insights or result.drivers) + len(result.trends or []))
    catalyst_base = min(20, 5 + 2 * len(catalyst_items))

    for node in result.key_stocks:
        name = (node.name or node.company or "").strip()
        code = (node.code or "").strip()
        key = code or _normalize_topic(name)
        if not key or key in seen:
            continue
        seen.add(key)

        earnings = min(20, 5 + (5 if node.role else 0) + (5 if node.description else 0) + (5 if node.metric else 0))
        valuation = min(20, 6 + (8 if node.market_share else 0) + (4 if node.confidence == "high" else 2 if node.confidence == "medium" else 0))
        evidence = min(20, 4 + min(9, 3 * len(node.evidence_ids)) + (3 if node.source else 0) + (4 if node.source_url else 0))
        risk = min(20, 2 * len(risk_items) + (5 if node.confidence == "low" else 0))
        total = max(0, min(100, prosperity_base + earnings + valuation + catalyst_base + evidence - risk // 2))
        rationale_parts = [part for part in (node.role, node.description, node.metric) if part]
        rationale = "；".join(rationale_parts[:2]) or "基于产业链角色与现有公开证据纳入研究跟踪。"
        opportunities.append(IndustryChainOpportunity(
            name=name or code,
            code=code,
            role=node.role,
            prosperity_score=prosperity_base,
            earnings_score=earnings,
            valuation_score=valuation,
            catalyst_score=catalyst_base,
            evidence_score=evidence,
            risk_score=risk,
            total_score=total,
            rationale=rationale,
            evidence_ids=list(node.evidence_ids),
        ))

    opportunities.sort(key=lambda item: (-item.total_score, item.code, item.name))
    return opportunities


__all__ = ["build_opportunities", "build_topic_resolution"]
