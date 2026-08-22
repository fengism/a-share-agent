"""Deterministic chart builders for normalized industry-chain results."""

from app.modules.industry_chain.models import IndustryChainChart, IndustryChainNode, IndustryChainResult

_MAX_TIER_NODES = 8
_MAX_COMPANIES_PER_NODE = 6


def _node_name(node: IndustryChainNode) -> str:
    return str(node.name or node.company or node.code or "未命名环节")[:80]


def _tree_node(node: IndustryChainNode) -> dict:
    children = [
        {"name": company[:80]}
        for company in node.companies[:_MAX_COMPANIES_PER_NODE]
        if company.strip()
    ]
    item: dict[str, object] = {"name": _node_name(node)}
    if children:
        item["children"] = children
    return item


def _tier(name: str, nodes: list[IndustryChainNode]) -> dict | None:
    children = [_tree_node(node) for node in nodes[:_MAX_TIER_NODES]]
    return {"name": name, "children": children} if children else None


def build_industry_charts(result: IndustryChainResult) -> list[IndustryChainChart]:
    tiers = [
        _tier("上游供给", result.upstream),
        _tier("核心环节", result.midstream),
        _tier("下游需求", result.downstream),
    ]
    children = [tier for tier in tiers if tier is not None]
    if not children:
        return []
    option = {
        "backgroundColor": "transparent",
        "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
        "series": [{
            "type": "tree",
            "data": [{"name": result.name or "产业链", "children": children}],
            "top": 20,
            "left": 80,
            "bottom": 20,
            "right": 80,
            "roam": True,
            "expandAndCollapse": True,
            "initialTreeDepth": 5,
            "lineStyle": {"color": "#4b5563", "width": 1.5},
            "label": {"position": "left", "fontSize": 12, "color": "#e5e7eb"},
            "leaves": {"label": {"position": "right", "fontSize": 12, "color": "#e5e7eb"}},
        }],
    }
    return [IndustryChainChart(
        title=f"{result.name or '产业'}产业链结构",
        description="根据结构化上游、中游和下游节点确定性生成",
        type="tree",
        option=option,
    )]
