"""跨链全局产业链图谱构建器。

遍历所有 AtlasChain，把公司节点按股票代码去重合并，
同链不同层之间的公司建立上下游关系边，返回适配 ECharts graph 的数据结构。
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from app.modules.industry_chain.atlas.contracts import AtlasChain
from app.modules.industry_chain.atlas.loader import list_atlas_chains

logger = logging.getLogger(__name__)

# 避免密集链条 O(n²) 爆炸，每层最多取前 N 家公司建边
_MAX_COMPANIES_PER_LAYER_FOR_EDGES = 5


class GraphNode(BaseModel):
    id: str
    name: str
    chains: list[str] = Field(default_factory=list)
    layer: str = ""
    segments: list[str] = Field(default_factory=list)
    chain_count: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    chain_slug: str = ""
    chain_name: str = ""
    relation: str = ""


class GraphSummary(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    total_chains: int = 0
    categories: list[str] = Field(default_factory=list)


class HubCompany(BaseModel):
    id: str
    name: str
    chain_count: int
    chains: list[str] = Field(default_factory=list)
    chain_names: list[str] = Field(default_factory=list)
    layer: str = ""
    segments: list[str] = Field(default_factory=list)


class ChainSynergy(BaseModel):
    source_slug: str
    source_name: str
    target_slug: str
    target_name: str
    shared_companies_count: int
    shared_companies: list[str] = Field(default_factory=list)


class AtlasGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    summary: GraphSummary = Field(default_factory=GraphSummary)
    chain_index: dict[str, str] = Field(default_factory=dict)
    hub_companies: list[HubCompany] = Field(default_factory=list)
    chain_synergies: list[ChainSynergy] = Field(default_factory=list)


# ── 层级关系映射 ──────────────────────────────────────────

_LAYER_PAIRS: list[tuple[str, str, str]] = [
    ("upstream", "midstream", "upstream_to_midstream"),
    ("midstream", "downstream", "midstream_to_downstream"),
    ("upstream", "downstream", "upstream_to_downstream"),
]


def _collect_layer_codes(
    chain: AtlasChain,
) -> dict[str, list[str]]:
    """提取每层前 N 家公司代码（保序去重）。"""
    result: dict[str, list[str]] = {}
    for layer in chain.layers:
        codes: list[str] = []
        seen: set[str] = set()
        for segment in layer.segments:
            for company in segment.companies:
                if company.code not in seen:
                    seen.add(company.code)
                    codes.append(company.code)
                if len(codes) >= _MAX_COMPANIES_PER_LAYER_FOR_EDGES:
                    break
            if len(codes) >= _MAX_COMPANIES_PER_LAYER_FOR_EDGES:
                break
        result[layer.key] = codes
    return result


def build_atlas_graph(
    chain_slugs: list[str] | None = None,
    user_id: int | None = None,
) -> AtlasGraph:
    """构建跨链全局产业链图谱。"""
    all_chains = list_atlas_chains(user_id=user_id)
    if chain_slugs:
        slug_set = set(chain_slugs)
        all_chains = [c for c in all_chains if c.slug in slug_set]

    # 节点聚合：公司代码 -> 聚合信息
    node_chains: dict[str, set[str]] = defaultdict(set)
    node_name: dict[str, str] = {}
    node_layers: dict[str, list[str]] = defaultdict(list)
    node_segments: dict[str, set[str]] = defaultdict(set)

    # 边收集
    edges: list[GraphEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()

    chain_index: dict[str, str] = {}
    category_set: set[str] = set()

    for chain in all_chains:
        chain_index[chain.slug] = chain.name
        category_set.add(chain.category)

        # 收集节点
        for layer in chain.layers:
            for segment in layer.segments:
                for company in segment.companies:
                    code = company.code
                    node_name[code] = company.name
                    node_chains[code].add(chain.slug)
                    node_layers[code].append(layer.key)
                    node_segments[code].add(segment.name)

        # 构建边
        layer_codes = _collect_layer_codes(chain)
        for src_key, tgt_key, relation in _LAYER_PAIRS:
            src_codes = layer_codes.get(src_key, [])
            tgt_codes = layer_codes.get(tgt_key, [])
            for src in src_codes:
                for tgt in tgt_codes:
                    if src == tgt:
                        continue
                    edge_key = (src, tgt, chain.slug)
                    if edge_key in edge_keys:
                        continue
                    edge_keys.add(edge_key)
                    edges.append(
                        GraphEdge(
                            source=src,
                            target=tgt,
                            chain_slug=chain.slug,
                            chain_name=chain.name,
                            relation=relation,
                        )
                    )

    # 生成节点
    nodes: list[GraphNode] = []
    for code in sorted(node_name):
        layer_counter = Counter(node_layers[code])
        primary_layer = layer_counter.most_common(1)[0][0] if layer_counter else ""
        nodes.append(
            GraphNode(
                id=code,
                name=node_name[code],
                chains=sorted(node_chains[code]),
                layer=primary_layer,
                segments=sorted(node_segments[code]),
                chain_count=len(node_chains[code]),
            )
        )

    # 跨链枢纽企业排行（参与产业链数量排序）
    sorted_nodes = sorted(nodes, key=lambda n: n.chain_count, reverse=True)
    hub_companies = [
        HubCompany(
            id=n.id,
            name=n.name,
            chain_count=n.chain_count,
            chains=n.chains,
            chain_names=[chain_index.get(slug, slug) for slug in n.chains],
            layer=n.layer,
            segments=n.segments,
        )
        for n in sorted_nodes
        if n.chain_count > 1
    ][:20]

    # 产业链协同共现分析（统计两两产业链共同关联的上市公司）
    chain_companies: dict[str, dict[str, str]] = defaultdict(dict)
    for chain in all_chains:
        for layer in chain.layers:
            for segment in layer.segments:
                for comp in segment.companies:
                    chain_companies[chain.slug][comp.code] = comp.name

    chain_synergies: list[ChainSynergy] = []
    slug_list = list(chain_index.keys())
    for i in range(len(slug_list)):
        s1 = slug_list[i]
        for j in range(i + 1, len(slug_list)):
            s2 = slug_list[j]
            c1_comps = chain_companies[s1]
            c2_comps = chain_companies[s2]
            common_codes = set(c1_comps.keys()) & set(c2_comps.keys())
            if common_codes:
                chain_synergies.append(
                    ChainSynergy(
                        source_slug=s1,
                        source_name=chain_index[s1],
                        target_slug=s2,
                        target_name=chain_index[s2],
                        shared_companies_count=len(common_codes),
                        shared_companies=sorted([c1_comps[code] for code in common_codes]),
                    )
                )
    chain_synergies.sort(key=lambda x: x.shared_companies_count, reverse=True)

    return AtlasGraph(
        nodes=nodes,
        edges=edges,
        summary=GraphSummary(
            total_nodes=len(nodes),
            total_edges=len(edges),
            total_chains=len(all_chains),
            categories=sorted(category_set),
        ),
        chain_index=chain_index,
        hub_companies=hub_companies,
        chain_synergies=chain_synergies,
    )
