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
    """仅按资料完整度排序；保留旧评分字段为零，不暗示基本面优劣。"""
    opportunities: list[IndustryChainOpportunity] = []
    seen: set[str] = set()
    for node in result.key_stocks:
        name = (node.name or node.company or "").strip()
        code = (node.code or "").strip()
        key = code or _normalize_topic(name)
        if not key or key in seen:
            continue
        seen.add(key)

        # Completeness is not an investment factor. Only linked successful evidence counts.
        valid_ids = {item.evidence_id for item in result.evidence_catalog if item.status == "success"}
        linked = set(node.evidence_ids) & valid_ids
        evidence = min(100, 25 * len(linked))
        completeness = sum(bool(value) for value in (node.role, node.description, node.metric, linked)) * 25
        rationale_parts = [part for part in (node.role, node.description, node.metric) if part]
        rationale = "；".join(rationale_parts[:2]) or "基于产业链角色与现有公开证据纳入研究跟踪。"
        opportunities.append(IndustryChainOpportunity(
            name=name or code,
            code=code,
            role=node.role,
            scoring_version=2,
            completeness_score=completeness,
            evidence_score=evidence,
            total_score=completeness,
            rationale=rationale,
            evidence_ids=list(node.evidence_ids),
        ))

    opportunities.sort(key=lambda item: (-item.total_score, item.code, item.name))
    return opportunities


__all__ = ["build_opportunities", "build_topic_resolution"]
