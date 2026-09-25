"""ECharts options for the industry-chain relationship graph."""

from html import escape

from app.modules.industry_chain.models import IndustryChainChart, IndustryChainNode, IndustryChainResult

_MAX_TIER_NODES = 10
_MAX_COMPANY_NODES = 2
_GRAPH_WIDTH = 1200
_TIER_START_Y = 230
_TIER_ROW_GAP = 72

_TIER_META = {
    "upstream": {
        "name": "上游供给",
        "subtitle": "核心部件 / 原材料",
        "color": "#1677ff",
        "soft_color": "#eaf3ff",
        "x": 180,
    },
    "midstream": {
        "name": "中游制造",
        "subtitle": "核心系统 / 整机集成",
        "color": "#722ed1",
        "soft_color": "#f4edff",
        "x": 600,
    },
    "downstream": {
        "name": "下游需求",
        "subtitle": "终端场景 / 客户应用",
        "color": "#389e0d",
        "soft_color": "#edf9e8",
        "x": 1020,
    },
}


def _node_name(node: IndustryChainNode) -> str:
    return str(node.name or node.company or node.code or "未命名环节")[:80]


def _short_label(value: str, limit: int) -> str:
    value = value.strip()
    return value if len(value) <= limit else f"{value[:limit]}…"


def _tooltip_line(label: str, value: str) -> str:
    return f"<b>{escape(label)}：</b>{escape(value)}"


def _stage_tooltip(node: IndustryChainNode) -> str:
    parts = [_tooltip_line("环节", _node_name(node))]
    if node.code:
        parts.append(_tooltip_line("代码", node.code))
    role_description = node.role or node.description
    if role_description:
        parts.append(_tooltip_line("角色/说明", role_description[:160]))
    metrics = " · ".join(item for item in (node.market_share, node.metric) if item)
    if metrics:
        parts.append(_tooltip_line("市场指标", metrics))
    companies = [company.strip() for company in node.companies if company.strip()]
    if companies:
        parts.append(_tooltip_line("代表公司", "、".join(companies)))
    return "<br/>".join(parts)


def _graph_node(
    *,
    node_id: str,
    name: str,
    x: int,
    y: int,
    category: int,
    color: str,
    border_color: str,
    symbol_size: list[int],
    label_color: str,
    tooltip: str,
    font_size: int = 13,
    font_weight: int | str = 600,
) -> dict:
    return {
        "id": node_id,
        "name": name,
        "x": x,
        "y": y,
        "category": category,
        "symbol": "roundRect",
        "symbolSize": symbol_size,
        "draggable": True,
        "itemStyle": {
            "color": color,
            "borderColor": border_color,
            "borderWidth": 1.5,
        },
        "label": {
            "show": True,
            "position": "inside",
            "color": label_color,
            "fontSize": font_size,
            "fontWeight": font_weight,
            "overflow": "truncate",
        },
        "tooltip": {"formatter": tooltip},
    }


def _graph_link(source: str, target: str, color: str, *, curveness: float = 0.0) -> dict:
    return {
        "source": source,
        "target": target,
        "lineStyle": {
            "color": color,
            "width": 1.4,
            "opacity": 0.48,
            "curveness": curveness,
        },
    }


def _append_tier(
    graph_nodes: list[dict],
    graph_links: list[dict],
    *,
    tier_key: str,
    nodes: list[IndustryChainNode],
    category: int,
) -> None:
    if not nodes:
        return

    meta = _TIER_META[tier_key]
    color = str(meta["color"])
    soft_color = str(meta["soft_color"])
    center_x = int(meta["x"])
    visible_nodes = nodes[:_MAX_TIER_NODES]
    tier_id = f"tier-{tier_key}"
    tier_name = f"{meta['name']}\n{len(visible_nodes)} 个环节"
    tier_tooltip = (
        _tooltip_line("层级", str(meta["name"]))
        + "<br/>"
        + _tooltip_line("定位", str(meta["subtitle"]))
        + "<br/>"
        + _tooltip_line("展示环节", str(len(visible_nodes)))
    )
    graph_nodes.append(_graph_node(
        node_id=tier_id,
        name=tier_name,
        x=center_x,
        y=130,
        category=category,
        color=color,
        border_color=color,
        symbol_size=[176, 52],
        label_color="#ffffff",
        tooltip=tier_tooltip,
        font_size=14,
        font_weight=700,
    ))
    graph_links.append(_graph_link("industry-root", tier_id, color, curveness=0.08))

    for index, node in enumerate(visible_nodes):
        stage_id = f"{tier_key}-stage-{index}"
        stage_y = _TIER_START_Y + index * _TIER_ROW_GAP
        stage_name = _node_name(node)
        graph_nodes.append(_graph_node(
            node_id=stage_id,
            name=_short_label(stage_name, 10),
            x=center_x,
            y=stage_y,
            category=category,
            color=soft_color,
            border_color=color,
            symbol_size=[142, 40],
            label_color="#172033",
            tooltip=_stage_tooltip(node),
        ))
        curve_direction = -1 if index % 2 else 1
        curve_size = 0.025 + min(index, 6) * 0.006
        graph_links.append(_graph_link(
            tier_id,
            stage_id,
            color,
            curveness=curve_direction * curve_size,
        ))

        companies = [company.strip() for company in node.companies if company.strip()][:_MAX_COMPANY_NODES]
        offsets = [118] if len(companies) == 1 else [-118, 118]
        for company_index, company in enumerate(companies):
            company_id = f"{tier_key}-stage-{index}-company-{company_index}"
            graph_nodes.append(_graph_node(
                node_id=company_id,
                name=_short_label(company, 7),
                x=center_x + offsets[company_index],
                y=stage_y,
                category=category,
                color="#ffffff",
                border_color=color,
                symbol_size=[96, 30],
                label_color="#334155",
                tooltip=(
                    _tooltip_line("代表公司", company)
                    + "<br/>"
                    + _tooltip_line("所属环节", stage_name)
                ),
                font_size=12,
                font_weight=500,
            ))
            graph_links.append(_graph_link(stage_id, company_id, color))


def build_industry_charts(result: IndustryChainResult) -> list[IndustryChainChart]:
    tier_groups = (
        ("upstream", result.upstream),
        ("midstream", result.midstream),
        ("downstream", result.downstream),
    )
    if not any(nodes for _, nodes in tier_groups):
        return []

    root_name = result.name.strip() or "产业链"
    graph_nodes = [_graph_node(
        node_id="industry-root",
        name=_short_label(root_name, 14),
        x=_GRAPH_WIDTH // 2,
        y=28,
        category=0,
        color="#0f4cbd",
        border_color="#0f4cbd",
        symbol_size=[206, 56],
        label_color="#ffffff",
        tooltip=_tooltip_line("产业链", root_name),
        font_size=16,
        font_weight=700,
    )]
    graph_links: list[dict] = []

    for category, (tier_key, nodes) in enumerate(tier_groups, start=1):
        _append_tier(
            graph_nodes,
            graph_links,
            tier_key=tier_key,
            nodes=nodes,
            category=category,
        )

    categories = [
        {"name": "产业核心", "itemStyle": {"color": "#0f4cbd"}},
        {"name": "上游供给", "itemStyle": {"color": _TIER_META["upstream"]["color"]}},
        {"name": "中游制造", "itemStyle": {"color": _TIER_META["midstream"]["color"]}},
        {"name": "下游需求", "itemStyle": {"color": _TIER_META["downstream"]["color"]}},
    ]
    option = {
        "backgroundColor": "transparent",
        "animationDuration": 500,
        "animationDurationUpdate": 350,
        "tooltip": {
            "trigger": "item",
            "triggerOn": "mousemove|click",
            "confine": True,
            "backgroundColor": "rgba(255, 255, 255, 0.98)",
            "borderColor": "#d7deea",
            "borderWidth": 1,
            "textStyle": {"color": "#172033", "fontSize": 13, "lineHeight": 20},
            "extraCssText": "max-width:360px;white-space:normal;overflow-wrap:anywhere;word-break:break-word;box-shadow:0 8px 28px rgba(15,23,42,.16);border-radius:8px;padding:10px 14px;",
        },
        "series": [{
            "type": "graph",
            "layout": "none",
            "data": graph_nodes,
            "links": graph_links,
            "categories": categories,
            "left": "3%",
            "right": "3%",
            "top": "5%",
            "bottom": "5%",
            "roam": True,
            "scaleLimit": {"min": 0.65, "max": 2.5},
            "edgeSymbol": ["none", "none"],
            "lineStyle": {
                "color": "source",
                "width": 1.4,
                "opacity": 0.48,
            },
            "emphasis": {
                "focus": "adjacency",
                "scale": 1.08,
                "lineStyle": {"width": 2.4, "opacity": 0.9},
            },
            "selectedMode": False,
        }],
    }
    return [IndustryChainChart(
        title=f"{root_name}产业链全景图谱",
        description="基于上中下游核心环节与代表公司构建的分层关系图（支持缩放、拖拽与关联高亮）",
        type="graph",
        option=option,
    )]


def build_relationship_chart(result: IndustryChainResult) -> IndustryChainChart | None:
    if not result.relationships:
        return None
    names = sorted({name for edge in result.relationships for name in (edge.source_node, edge.target_node)})
    labels = {"supply": "供货", "purchase": "采购", "substitute": "替代", "compete": "竞争", "transmission": "定性传导"}
    return IndustryChainChart(
        title="关系与定性传导",
        description="箭头由起点指向目标；传导为条件假设，不代表确定收益。具体依据和失效条件见关系卡片。",
        type="graph",
        option={
            "tooltip": {"trigger": "item", "confine": True},
            "series": [{
                "type": "graph", "layout": "circular", "roam": True,
                "label": {"show": True}, "edgeSymbol": ["none", "arrow"],
                "data": [{"id": name, "name": name, "symbolSize": 45,
                          "tooltip": {"formatter": escape(name)}} for name in names],
                "links": [{
                    "source": edge.source_node, "target": edge.target_node,
                    "label": {"show": True, "formatter": labels[edge.relation_type]},
                    "lineStyle": {"type": "dashed" if edge.claim_type != "fact" else "solid", "curveness": 0.15},
                    "tooltip": {"formatter": escape(edge.detail or edge.title)},
                } for edge in result.relationships],
            }],
        },
    )
