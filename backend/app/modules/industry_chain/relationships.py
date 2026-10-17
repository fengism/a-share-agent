"""Conservative validation of company exposure and qualitative relationships."""

import re

from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.numbers import normalize_number_text, number_tokens


def validate_relationships(result: IndustryChainResult) -> None:
    nodes = [*result.upstream, *result.midstream, *result.downstream, *result.key_stocks]
    known = {
        name.strip()
        for node in nodes
        for name in [node.name or "", node.company or "", *node.companies]
        if name.strip()
    }
    valid_ids = {item.evidence_id for item in result.evidence_catalog if item.status == "success"}
    accepted = []
    seen = set()
    for edge in result.relationships:
        key = (edge.source_node.strip(), edge.target_node.strip(), edge.relation_type)
        if key in seen:
            continue
        seen.add(key)
        if key[0] not in known or key[1] not in known or key[0] == key[1]:
            result.warnings.append(f"关系端点无法映射到报告节点，已移除：{edge.title}")
            result.quality_status = "degraded"
            continue
        if not set(edge.evidence_ids) & valid_ids:
            result.warnings.append(f"缺少关系证据，已移除：{edge.title}")
            result.quality_status = "degraded"
            continue
        edge.source_node, edge.target_node = key[:2]
        if edge.relation_type == "transmission":
            edge.claim_type = "inference"
            if not edge.conditions:
                edge.confidence = "low"
                edge.verification_notes.append("传导条件尚未明确，不代表已实现的财务影响。")
        elif edge.verification_status != "quote_matched":
            edge.claim_type = "inference"
            edge.confidence = "low"
        accepted.append(edge)
    result.relationships = accepted
    for node in nodes:
        # A model-selected category alone cannot establish revenue exposure.
        if node.business_relevance in {"business", "earnings"} and node.verification_status != "quote_matched":
            node.business_relevance = "unverified"
            node.verification_notes.append("业务或业绩相关度缺少原文匹配，待验证。")
        share = number_tokens(node.revenue_share)
        period = re.compile(rf"(?<![0-9]){re.escape(node.revenue_period.strip())}(?![0-9])")
        matched_share = (
            len(share) == 1
            and share[0][1] == "%"
            and 0 <= share[0][0] <= 100
            and bool(node.revenue_period.strip())
            and any(
                share[0] in number_tokens(citation.quote) and period.search(normalize_number_text(citation.quote))
                for citation in node.citations
            )
        )
        if node.revenue_share and not matched_share:
            node.revenue_share = ""
            node.revenue_period = ""
            node.verification_notes.append("收入占比或统计期未匹配到原文，已移除。")
        if node.business_relevance == "earnings" and not node.revenue_share:
            node.business_relevance = "unverified"
            node.verification_notes.append("未验证相关收入占比，不能标记为业绩相关。")


def build_node_adjacency_map(result: IndustryChainResult) -> dict[str, dict[str, list[str]]]:
    """构建产业链节点关系图谱邻接索引，方便拓扑上下游与竞品关系双向快速检索。"""
    adjacency: dict[str, dict[str, list[str]]] = {}

    def _ensure_node(node_name: str) -> None:
        if node_name not in adjacency:
            adjacency[node_name] = {
                "upstream": [],
                "downstream": [],
                "compete": [],
                "substitute": [],
                "transmission": [],
            }

    for edge in result.relationships:
        src = (edge.source_node or "").strip()
        tgt = (edge.target_node or "").strip()
        rel = edge.relation_type
        if not src or not tgt:
            continue
        _ensure_node(src)
        _ensure_node(tgt)

        if rel == "supply":
            if src not in adjacency[tgt]["upstream"]:
                adjacency[tgt]["upstream"].append(src)
            if tgt not in adjacency[src]["downstream"]:
                adjacency[src]["downstream"].append(tgt)
        elif rel == "purchase":
            if tgt not in adjacency[src]["upstream"]:
                adjacency[src]["upstream"].append(tgt)
            if src not in adjacency[tgt]["downstream"]:
                adjacency[tgt]["downstream"].append(src)
        elif rel in ("compete", "substitute", "transmission"):
            if tgt not in adjacency[src][rel]:
                adjacency[src][rel].append(tgt)
            if rel in ("compete", "substitute") and src not in adjacency[tgt][rel]:
                adjacency[tgt][rel].append(src)

    return adjacency
