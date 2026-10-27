"""ECharts options for the industry-chain relationship graph."""

import re
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
    graph_nodes.append(
        _graph_node(
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
        )
    )
    graph_links.append(_graph_link("industry-root", tier_id, color, curveness=0.08))

    for index, node in enumerate(visible_nodes):
        stage_id = f"{tier_key}-stage-{index}"
        stage_y = _TIER_START_Y + index * _TIER_ROW_GAP
        stage_name = _node_name(node)
        graph_nodes.append(
            _graph_node(
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
            )
        )
        curve_direction = -1 if index % 2 else 1
        curve_size = 0.025 + min(index, 6) * 0.006
        graph_links.append(
            _graph_link(
                tier_id,
                stage_id,
                color,
                curveness=curve_direction * curve_size,
            )
        )

        companies = [company.strip() for company in node.companies if company.strip()][:_MAX_COMPANY_NODES]
        offsets = [118] if len(companies) == 1 else [-118, 118]
        for company_index, company in enumerate(companies):
            company_id = f"{tier_key}-stage-{index}-company-{company_index}"
            graph_nodes.append(
                _graph_node(
                    node_id=company_id,
                    name=_short_label(company, 7),
                    x=center_x + offsets[company_index],
                    y=stage_y,
                    category=category,
                    color="#ffffff",
                    border_color=color,
                    symbol_size=[96, 30],
                    label_color="#334155",
                    tooltip=(_tooltip_line("代表公司", company) + "<br/>" + _tooltip_line("所属环节", stage_name)),
                    font_size=12,
                    font_weight=500,
                )
            )
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
    graph_nodes = [
        _graph_node(
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
        )
    ]
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
        "series": [
            {
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
            }
        ],
    }
    charts = [
        IndustryChainChart(
            title=f"{root_name}产业链全景图谱",
            description="基于上中下游核心环节与代表公司构建的分层关系图（支持缩放、拖拽与关联高亮）",
            type="graph",
            option=option,
        )
    ]
    val_chart = build_value_distribution_chart(result)
    if val_chart is not None:
        charts.append(val_chart)
    matrix_chart = build_stock_valuation_matrix_chart(result)
    if matrix_chart is not None:
        charts.append(matrix_chart)
    overseas_chart = build_overseas_exposure_chart(result)
    if overseas_chart is not None:
        charts.append(overseas_chart)
    return charts


def _parse_percent(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(value))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_float(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_market_cap_billions(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(亿|万)?", str(value))
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit == "万":
            return val / 10000.0
        return val
    return None


def build_value_distribution_chart(result: IndustryChainResult) -> IndustryChainChart | None:
    """基于 BOM 成本占比与毛利率区间构建价值链与利润池拆解双轴图。"""
    if not getattr(result, "value_distribution", None):
        return None

    segments: list[str] = []
    cost_shares: list[float] = []
    gross_margins: list[float] = []
    pricing_powers: list[str] = []

    for item in result.value_distribution:
        seg = item.segment or "未命名环节"
        cost_val = _parse_percent(item.cost_share)
        gm_val = _parse_percent(item.gross_margin_range)
        if cost_val is None and gm_val is None:
            continue
        segments.append(seg)
        cost_shares.append(cost_val if cost_val is not None else 0.0)
        gross_margins.append(gm_val if gm_val is not None else 0.0)
        pricing_powers.append(item.pricing_power)

    if not segments:
        return None

    power_color_map = {
        "high": "#16a34a",
        "medium": "#0284c7",
        "low": "#d97706",
        "unverified": "#64748b",
    }
    bar_data = [
        {
            "name": seg,
            "value": cost,
            "itemStyle": {"color": power_color_map.get(power, "#0284c7")},
        }
        for seg, cost, power in zip(segments, cost_shares, pricing_powers)
    ]

    option = {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "confine": True,
        },
        "legend": {
            "data": ["BOM 成本占比 (%)", "毛利率中枢 (%)"],
            "top": "3%",
            "textStyle": {"color": "#334155"},
        },
        "grid": {
            "left": "5%",
            "right": "5%",
            "top": "16%",
            "bottom": "14%",
            "containLabel": True,
        },
        "xAxis": {
            "type": "category",
            "data": segments,
            "axisLabel": {"interval": 0, "rotate": 25 if len(segments) > 4 else 0, "fontSize": 12},
        },
        "yAxis": [
            {
                "type": "value",
                "name": "BOM 成本占比 (%)",
                "min": 0,
                "axisLabel": {"formatter": "{value}%"},
            },
            {
                "type": "value",
                "name": "毛利率 (%)",
                "min": 0,
                "axisLabel": {"formatter": "{value}%"},
            },
        ],
        "series": [
            {
                "name": "BOM 成本占比 (%)",
                "type": "bar",
                "data": bar_data,
                "barMaxWidth": 36,
                "label": {"show": True, "position": "top", "formatter": "{c}%"},
            },
            {
                "name": "毛利率中枢 (%)",
                "type": "line",
                "yAxisIndex": 1,
                "data": gross_margins,
                "itemStyle": {"color": "#dc2626"},
                "lineStyle": {"width": 2.5},
                "symbol": "circle",
                "symbolSize": 7,
                "label": {"show": True, "position": "top", "formatter": "{c}%"},
            },
        ],
    }

    return IndustryChainChart(
        title=f"{result.name or '产业链'}价值链 BOM 成本与毛利分布",
        description="拆解各核心环节/零部件的单机价值量（BOM）占比与毛利率中枢，柱形颜色按环节议价定价权区分",
        type="bar",
        option=option,
    )


def build_stock_valuation_matrix_chart(result: IndustryChainResult) -> IndustryChainChart | None:
    """基于重点标的动态 PE、ROE 资本回报与总市值构建投资四象限矩阵图。"""
    if not getattr(result, "key_stocks", None):
        return None

    valid_stocks: list[dict] = []
    for s in result.key_stocks:
        pe_val = _parse_float(s.pe)
        roe_val = _parse_percent(s.roe)
        cap_val = _parse_market_cap_billions(s.total_market_cap)
        if pe_val is not None and roe_val is not None and pe_val > 0:
            valid_stocks.append({
                "name": s.name or s.company or s.code or "重点标的",
                "code": s.code or "",
                "pe": pe_val,
                "roe": roe_val,
                "market_cap": cap_val if cap_val is not None else 50.0,
                "cap_str": s.total_market_cap or "--",
            })

    if len(valid_stocks) < 2:
        return None

    cap_list = [item["market_cap"] for item in valid_stocks]
    max_cap = max(cap_list) if cap_list else 100.0

    series_data = []
    for item in valid_stocks:
        size = int(max(14, min(48, 14 + (item["market_cap"] / max(max_cap, 1.0)) * 34)))
        name_str = f"{item['name']}" + (f" ({item['code']})" if item['code'] else "")
        series_data.append({
            "name": name_str,
            "value": [item["pe"], item["roe"], item["market_cap"], item["cap_str"]],
            "symbolSize": size,
            "itemStyle": {"color": "#0284c7", "opacity": 0.85, "borderColor": "#0369a1", "borderWidth": 1.5},
        })

    pe_list = [item["pe"] for item in valid_stocks]
    roe_list = [item["roe"] for item in valid_stocks]
    median_pe = sorted(pe_list)[len(pe_list) // 2]
    median_roe = sorted(roe_list)[len(roe_list) // 2]

    option = {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "item",
            "confine": True,
            "formatter": "function(p) { var d = p.value; return '<b>' + p.name + '</b><br/>PE(动): ' + d[0] + 'x<br/>ROE: ' + d[1] + '%<br/>总市值: ' + d[3]; }",
        },
        "grid": {
            "left": "6%",
            "right": "6%",
            "top": "14%",
            "bottom": "12%",
            "containLabel": True,
        },
        "xAxis": {
            "name": "动态 PE (倍)",
            "type": "value",
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e2e8f0"}},
        },
        "yAxis": {
            "name": "ROE 净资产收益率 (%)",
            "type": "value",
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e2e8f0"}},
        },
        "series": [
            {
                "type": "scatter",
                "data": series_data,
                "label": {
                    "show": True,
                    "formatter": "{b}",
                    "position": "top",
                    "fontSize": 11,
                    "fontWeight": 600,
                    "color": "#0f172a",
                },
                "markLine": {
                    "silent": True,
                    "lineStyle": {"color": "#94a3b8", "type": "dotted", "width": 1.5},
                    "data": [
                        {"xAxis": median_pe, "label": {"formatter": f"PE中枢: {median_pe:.1f}x", "position": "end"}},
                        {"yAxis": median_roe, "label": {"formatter": f"ROE中枢: {median_roe:.1f}%", "position": "end"}},
                    ],
                },
            }
        ],
    }

    return IndustryChainChart(
        title=f"{result.name or '产业链'}核心标的估值与资本回报象限图",
        description="横轴为动态市盈率（PE），纵轴为净资产收益率（ROE），气泡大小对应总市值，虚线划分为行业中枢四象限",
        type="scatter",
        option=option,
    )


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
            "series": [
                {
                    "type": "graph",
                    "layout": "circular",
                    "roam": True,
                    "label": {"show": True},
                    "edgeSymbol": ["none", "arrow"],
                    "data": [
                        {"id": name, "name": name, "symbolSize": 45, "tooltip": {"formatter": escape(name)}}
                        for name in names
                    ],
                    "links": [
                        {
                            "source": edge.source_node,
                            "target": edge.target_node,
                            "label": {"show": True, "formatter": labels[edge.relation_type]},
                            "lineStyle": {
                                "type": "dashed" if edge.claim_type != "fact" else "solid",
                                "curveness": 0.15,
                            },
                            "tooltip": {"formatter": escape(edge.detail or edge.title)},
                        }
                        for edge in result.relationships
                    ],
                }
            ],
        },
    )


def build_overseas_exposure_chart(result: IndustryChainResult) -> IndustryChainChart | None:
    """基于重点标的出海与海外营收占比构建全球化与出口敞口对比横向柱状图。"""
    if not getattr(result, "key_stocks", None):
        return None

    valid_items: list[dict] = []
    for s in result.key_stocks:
        overseas_str = getattr(s, "overseas_share", "") or ""
        pct = _parse_percent(overseas_str)
        if pct is not None and pct > 0:
            name = (s.name or s.company or s.code or "重点标的").strip()
            code_str = f" ({s.code})" if s.code else ""
            valid_items.append({
                "label": f"{name}{code_str}",
                "name": name,
                "code": s.code or "",
                "pct": pct,
                "desc": overseas_str,
                "gross_margin": getattr(s, "gross_margin", "") or "--",
            })

    if len(valid_items) < 2:
        return None

    valid_items.sort(key=lambda x: x["pct"])
    y_labels = [item["label"] for item in valid_items]
    bar_data = []
    for item in valid_items:
        pct = item["pct"]
        color = "#0284c7" if pct >= 70.0 else "#38bdf8" if pct >= 30.0 else "#94a3b8"
        bar_data.append({
            "name": item["label"],
            "value": pct,
            "raw_desc": item["desc"],
            "gross_margin": item["gross_margin"],
            "itemStyle": {
                "color": color,
                "borderRadius": [0, 4, 4, 0],
            },
        })

    option = {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "confine": True,
            "formatter": "function(params) { var p = params[0]; var d = p.data; return '<b>' + p.name + '</b><br/>海外营收占比: <b>' + p.value + '%</b><br/>出海详情: ' + (d.raw_desc || '--') + '<br/>公司综合毛利率: ' + d.gross_margin; }",
        },
        "grid": {
            "left": "4%",
            "right": "8%",
            "top": "8%",
            "bottom": "8%",
            "containLabel": True,
        },
        "xAxis": {
            "type": "value",
            "name": "海外营收占比 (%)",
            "min": 0,
            "max": 100,
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e2e8f0"}},
            "axisLabel": {"formatter": "{value}%"},
        },
        "yAxis": {
            "type": "category",
            "data": y_labels,
            "axisLabel": {"interval": 0, "fontSize": 12, "color": "#1e293b"},
        },
        "series": [
            {
                "name": "海外营收占比 (%)",
                "type": "bar",
                "data": bar_data,
                "barMaxWidth": 28,
                "label": {
                    "show": True,
                    "position": "right",
                    "formatter": "{c}%",
                    "fontWeight": 600,
                    "color": "#0369a1",
                },
                "markLine": {
                    "silent": True,
                    "lineStyle": {"color": "#cbd5e1", "type": "dotted"},
                    "data": [
                        {"xAxis": 50, "label": {"formatter": "出海主导 (50%)", "position": "end"}},
                    ],
                },
            }
        ],
    }

    return IndustryChainChart(
        title=f"{result.name or '产业链'}重点标的海外营收占比与出海敞口对比",
        description="统计各核心标的海外或出口业务营收占比（%）及出海毛利率，直观对比出海全球化渗透度与外贸关税敏感度",
        type="bar",
        option=option,
    )
