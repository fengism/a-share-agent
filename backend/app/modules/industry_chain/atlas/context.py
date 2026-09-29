"""Resolve and render optional Atlas priors for one industry-chain run."""

from __future__ import annotations

from app.modules.industry_chain.atlas.contracts import AtlasChain
from app.modules.industry_chain.atlas.loader import get_atlas_chain, list_atlas_chains
from app.modules.industry_chain.atlas.miner import mining_slug


def matching_atlas_chain(name: str) -> AtlasChain | None:
    normalized = name.strip()
    chains = list_atlas_chains()
    exact = [chain for chain in chains if chain.name == normalized or normalized in (chain.aliases or [])]
    curated = [chain for chain in exact if not chain.slug.startswith("auto-")]
    matched = (curated or exact)[0] if len(curated or exact) == 1 else None
    if matched is None and not exact:
        matched = get_atlas_chain(mining_slug(normalized))
    if matched is None and not exact and len(normalized) >= 2:
        partial = [chain for chain in chains if (
            normalized in chain.name or chain.name in normalized
            or any(alias and (normalized in alias or alias in normalized) for alias in (chain.aliases or []))
        ) and not chain.slug.startswith("auto-")]
        matched = partial[0] if len(partial) == 1 else None
    return matched


def render_atlas_prior(matched: AtlasChain | None) -> str:
    if matched is None:
        return "无"
    lines = [f"知识库链条：{matched.name}（{matched.category}，来源：{matched.source}）"]
    if matched.summary:
        lines.append(f"概要：{matched.summary}")
    for layer in matched.layers:
        segments = "；".join(
            f"{segment.name}：{segment.description[:100]}（{'、'.join(company.name for company in segment.companies[:4])}）"
            for segment in layer.segments[:6]
        )
        lines.append(f"{layer.name}：{segments}")
    return "\n".join(lines)[:4000]


def atlas_expected_segments(matched: AtlasChain | None) -> dict[str, list[str]]:
    if matched is None:
        return {}
    return {
        layer.key: [segment.name for segment in layer.segments if segment.name.strip()]
        for layer in matched.layers
    }
