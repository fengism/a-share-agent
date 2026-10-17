"""基于 Playwright Headless 浏览器的产业链深度投研 PDF 生成服务。"""

from __future__ import annotations

import html
import logging
from typing import Any
from urllib.parse import urlsplit

from app.infrastructure.pdf_runtime import render_pdf
from app.modules.industry_chain.models import (
    IndustryChainInsight,
    IndustryChainNode,
    IndustryChainResult,
)
from app.modules.industry_chain.presentation import presentation_payload

logger = logging.getLogger(__name__)


def _esc(text: Any) -> str:
    """安全转义 HTML 字符串。"""
    if text is None:
        return ""
    return html.escape(str(text))


def _safe_url(value: str) -> str:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return ""
    return value.strip() if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _render_source_badge(source: str, url: str) -> str:
    s = _esc(source or "来源")
    u = _safe_url(url)
    if u:
        return f'<a href="{u}" target="_blank" style="color:#0284c7; text-decoration:none; font-size:10px; background:#e0f2fe; padding:1px 6px; border-radius:3px;">{s} ↗</a>'
    if source:
        return f'<span style="color:#64748b; font-size:10px; background:#f1f5f9; padding:1px 6px; border-radius:3px;">{s}</span>'
    return ""


def _render_evidence_tags(evidence_ids: list[str]) -> str:
    if not evidence_ids:
        return ""
    tags = "".join(
        f'<span style="display:inline-block; font-size:9px; color:#475569; background:#f1f5f9; border:1px solid #e2e8f0; padding:1px 4px; border-radius:3px; margin-right:3px; margin-top:2px;">{_esc(it)}</span>'
        for it in evidence_ids
    )
    return tags


def _render_claim_pill(claim_type: str, confidence: str) -> str:
    claim_map = {
        "fact": ("事实", "#dcfce7", "#166534"),
        "inference": ("推断", "#fef3c7", "#92400e"),
        "opinion": ("观点", "#e0e7ff", "#3730a3"),
    }
    conf_map = {"high": "高置信度", "medium": "中置信度", "low": "低置信度"}
    cl_label, cl_bg, cl_fg = claim_map.get(claim_type, ("研判", "#f1f5f9", "#475569"))
    conf_label = conf_map.get(confidence, "中置信度")
    return (
        f'<span style="display:inline-flex; align-items:center; gap:4px; font-size:10px; font-weight:600; padding:1px 6px; border-radius:4px; background:{cl_bg}; color:{cl_fg};">'
        f"{cl_label} · {conf_label}</span>"
    )


def _truncate_graph_label(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: max(limit - 1, 1)]}…"


def _node_companies(node: IndustryChainNode) -> str:
    companies = [company.strip() for company in node.companies if company.strip()]
    if companies:
        return "、".join(companies)
    return str(node.company or "").strip()


def _render_panorama_graph(result: IndustryChainResult) -> str:
    # 使用内嵌 SVG，避免 PDF 导出依赖前端 ECharts 或外部网络资源。
    tiers = (
        ("上游供给", "原材料 · 核心零部件", result.upstream, "#0284c7", "#f0f9ff"),
        ("中游制造", "生产制造 · 系统集成", result.midstream, "#16a34a", "#f0fdf4"),
        ("下游需求", "终端应用 · 客户场景", result.downstream, "#d97706", "#fffbeb"),
    )
    if not any(nodes for _, _, nodes, _, _ in tiers):
        return ""

    width = 960
    centers = (170, 480, 790)
    column_width = 270
    root_width = 230
    root_height = 52
    root_x = (width - root_width) // 2
    root_y = 20
    tier_y = 108
    tier_height = 50
    node_y = 192
    node_height = 48
    row_gap = 62
    max_nodes = 10
    visible_counts = [min(len(nodes), max_nodes) for _, _, nodes, _, _ in tiers]
    graph_rows = max(max(visible_counts), 1)
    has_omitted = any(len(nodes) > max_nodes for _, _, nodes, _, _ in tiers)
    svg_height = node_y + graph_rows * row_gap + (24 if has_omitted else 0)

    root_label = _esc(_truncate_graph_label(result.name or "产业链", 16))
    parts = [
        f'''<svg viewBox="0 0 {width} {svg_height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{root_label}产业链全景图谱">
        <defs>
            <filter id="panorama-shadow" x="-15%" y="-20%" width="130%" height="150%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.12"/>
            </filter>
            <marker id="panorama-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
                <path d="M0,0 L7,3.5 L0,7 Z" fill="#94a3b8"/>
            </marker>
        </defs>
        <rect x="{root_x}" y="{root_y}" width="{root_width}" height="{root_height}" rx="14" fill="#0f4cbd" filter="url(#panorama-shadow)"/>
        <text x="480" y="52" text-anchor="middle" fill="#ffffff" font-size="18" font-weight="700">{root_label}</text>'''
    ]

    for center, (title, subtitle, nodes, color, soft_color) in zip(centers, tiers, strict=True):
        parts.append(
            f'<path d="M480 72 C480 88 {center} 88 {center} {tier_y}" '
            'fill="none" stroke="#94a3b8" stroke-width="2" marker-end="url(#panorama-arrow)"/>'
        )
        tier_x = center - column_width // 2
        parts.append(f'''
        <rect x="{tier_x}" y="{tier_y}" width="{column_width}" height="{tier_height}" rx="12" fill="{color}" filter="url(#panorama-shadow)"/>
        <text x="{center}" y="130" text-anchor="middle" fill="#ffffff" font-size="15" font-weight="700">{_esc(title)}</text>
        <text x="{center}" y="148" text-anchor="middle" fill="#ffffff" fill-opacity="0.86" font-size="11">{_esc(subtitle)} · {len(nodes)} 个环节</text>''')

        visible_nodes = nodes[:max_nodes]
        if not visible_nodes:
            parts.append(f'''
        <line x1="{center}" y1="{tier_y + tier_height}" x2="{center}" y2="{node_y}" stroke="{color}" stroke-width="1.5" stroke-opacity="0.45"/>
        <rect x="{tier_x + 10}" y="{node_y}" width="{column_width - 20}" height="{node_height}" rx="10" fill="#ffffff" stroke="{color}" stroke-opacity="0.35" stroke-dasharray="5 4"/>
        <text x="{center}" y="{node_y + 29}" text-anchor="middle" fill="#94a3b8" font-size="12">暂无结构化环节</text>''')
            continue

        for index, node in enumerate(visible_nodes):
            current_y = node_y + index * row_gap
            line_start = tier_y + tier_height if index == 0 else current_y - (row_gap - node_height)
            parts.append(
                f'<line x1="{center}" y1="{line_start}" x2="{center}" y2="{current_y}" '
                f'stroke="{color}" stroke-width="1.5" stroke-opacity="0.5" marker-end="url(#panorama-arrow)"/>'
            )
            label = _esc(_truncate_graph_label(node.name or node.company or "核心环节", 16))
            companies = _esc(_truncate_graph_label(_node_companies(node), 22))
            parts.append(f'''
        <rect x="{tier_x + 10}" y="{current_y}" width="{column_width - 20}" height="{node_height}" rx="10" fill="{soft_color}" stroke="{color}" stroke-opacity="0.55"/>
        <circle cx="{tier_x + 28}" cy="{current_y + 17}" r="5" fill="{color}"/>
        <text x="{tier_x + 40}" y="{current_y + 21}" fill="#172033" font-size="13" font-weight="700">{label}</text>''')
            if companies:
                parts.append(
                    f'<text x="{tier_x + 28}" y="{current_y + 39}" fill="#64748b" font-size="10.5">代表：{companies}</text>'
                )

        omitted = len(nodes) - len(visible_nodes)
        if omitted > 0:
            omitted_y = node_y + len(visible_nodes) * row_gap - 5
            parts.append(
                f'<text x="{center}" y="{omitted_y}" text-anchor="middle" fill="#64748b" font-size="10.5">'
                f"另有 {omitted} 个环节，详见下表</text>"
            )

    parts.append("</svg>")
    svg = "".join(parts)
    return f"""
        <div class="panorama-block" data-testid="industry-chain-panorama">
            <div class="panorama-heading">
                <div>
                    <strong>产业链全景图谱</strong>
                    <span>上中下游核心环节与代表公司关系</span>
                </div>
                <div class="panorama-legend"><i class="upstream-dot"></i>上游 <i class="midstream-dot"></i>中游 <i class="downstream-dot"></i>下游</div>
            </div>
            {svg}
        </div>
    """


def generate_industry_chain_pdf_html(result: IndustryChainResult) -> str:
    """生成完整展开产业链上下游、市场规模、竞争格局与标的映射的机构级 A4 研报 HTML。"""
    result = IndustryChainResult.model_validate(presentation_payload(result))
    name = result.name or "核心产业链"
    aliases_str = " / ".join(result.aliases) if result.aliases else ""
    summary = result.summary or "暂无产业链概述数据"
    positioning = result.positioning or "暂无战略定位数据"
    quality_status = result.quality_status
    quality_label = "A · 完整研报 (High Quality)" if quality_status == "complete" else "B · 降级分析 (Degraded)"
    quality_bg = "#dcfce7" if quality_status == "complete" else "#fef3c7"
    quality_fg = "#166534" if quality_status == "complete" else "#92400e"

    scope = result.research_scope or {}
    region_map = {"china": "中国市场", "global": "全球市场", "china_and_global": "中国与全球市场"}
    scope_region = region_map.get(scope.get("region", ""), scope.get("region", "全市场"))
    scope_company = "A 股上市公司" if scope.get("company_scope") == "a_share" else "全公开企业"
    date_range = (
        f"{scope.get('start_date', '')} 至 {scope.get('end_date', '')}"
        if scope.get("start_date") and scope.get("end_date")
        else "近一年最新动态"
    )

    # 证据覆盖统计
    stats = result.evidence_stats
    coverage = result.coverage
    coverage_dict = coverage.model_dump() if hasattr(coverage, "model_dump") else {}
    complete_count = sum(1 for v in coverage_dict.values() if v == "complete")
    total_metrics = max(len(coverage_dict), 1)
    coverage_percent = int((complete_count / total_metrics) * 100)

    # 1. 市场规模指标
    metrics_cards_html = ""
    if result.market_metrics:
        cards = []
        for m in result.market_metrics:
            source_badge = _render_source_badge(m.source, m.source_url)
            growth_badge = (
                f'<span style="color:#16a34a; font-weight:700; margin-left:6px;">↑ {m.growth}</span>'
                if m.growth
                else ""
            )
            period_str = f'<span style="color:#64748b; font-size:10px;">({m.period})</span>' if m.period else ""
            cards.append(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="font-size:11px; color:#64748b; margin-bottom:4px;">{_esc(m.label)} {period_str}</div>
                <div style="font-size:16px; font-weight:800; color:#0f172a; margin-bottom:4px;">{_esc(m.value)} {growth_badge}</div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    {source_badge}
                    <div>{_render_evidence_tags(m.evidence_ids)}</div>
                </div>
            </div>
            """)
        metrics_cards_html = f'<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-top:8px;">{"".join(cards)}</div>'

    # 2. 上中下游图谱与环节表
    panorama_html = _render_panorama_graph(result)
    chain_rows_html = ""
    for stage_label, nodes, stage_color, stage_bg in (
        ("上游原材料/核心零部件", result.upstream, "#0284c7", "#f0f9ff"),
        ("中游生产制造/系统集成", result.midstream, "#16a34a", "#f0fdf4"),
        ("下游终端应用/客户场景", result.downstream, "#d97706", "#fffbeb"),
    ):
        if not nodes:
            continue
        for idx, node in enumerate(nodes):
            companies_str = "、".join(node.companies) if node.companies else (node.company or "--")
            share_badge = (
                f'<span style="display:inline-block; font-size:10px; color:#475569; background:#f1f5f9; padding:1px 5px; border-radius:3px; margin-left:4px;">份额: {_esc(node.market_share)}</span>'
                if node.market_share
                else ""
            )
            source_badge = _render_source_badge(node.source, node.source_url)
            evidence_tags = _render_evidence_tags(node.evidence_ids)

            stage_cell = (
                f'<td rowspan="{len(nodes)}" style="background:{stage_bg}; color:{stage_color}; font-weight:700; font-size:11px; text-align:center; vertical-align:middle; width:100px; border-right:1px solid #e2e8f0;">{stage_label}</td>'
                if idx == 0
                else ""
            )
            chain_rows_html += f"""
            <tr style="border-bottom:1px solid #f1f5f9;">
                {stage_cell}
                <td style="padding:8px 10px; font-weight:600; color:#0f172a; font-size:11px; width:130px;">
                    {_esc(node.name or node.company or "核心环节")}
                </td>
                <td style="padding:8px 10px; font-size:11px; color:#475569; line-height:1.45;">
                    {_esc(node.role or node.description or "--")}
                </td>
                <td style="padding:8px 10px; font-size:11px; color:#0f172a; font-weight:500; width:180px;">
                    {_esc(companies_str)} {share_badge}
                </td>
                <td style="padding:8px 10px; width:120px; text-align:right;">
                    <div>{source_badge}</div>
                    <div>{evidence_tags}</div>
                </td>
            </tr>
            """

    # 3. 技术路线
    tech_html = ""
    if result.technology_routes:
        tech_cards = []
        for t in result.technology_routes:
            claim_pill = _render_claim_pill(t.claim_type, t.confidence)
            source_badge = _render_source_badge(t.source, t.source_url)
            evidence_tags = _render_evidence_tags(t.evidence_ids)
            tech_cards.append(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <strong style="font-size:12px; color:#0f172a;">{_esc(t.title)}</strong>
                    {claim_pill}
                </div>
                <div style="font-size:11px; color:#334155; line-height:1.5; margin-bottom:6px;">{_esc(t.detail or t.evidence or "--")}</div>
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px; color:#64748b;">
                    <div>{source_badge}</div>
                    <div>{evidence_tags}</div>
                </div>
            </div>
            """)
        tech_html = f'<div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:10px; margin-top:8px;">{"".join(tech_cards)}</div>'

    # 4. 竞争格局
    comp_html = ""
    if result.competition:
        comp_cards = []
        for group in result.competition:
            company_pills = "".join(
                f'<span style="display:inline-block; font-size:10px; color:#0f172a; background:#f8fafc; border:1px solid #cbd5e1; padding:2px 6px; border-radius:4px; margin-right:4px; margin-bottom:4px;">{_esc(c.name or c.company or c.code)}</span>'
                for c in group.companies
            )
            comp_cards.append(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px; margin-bottom:8px;">
                <div style="font-size:12px; font-weight:700; color:#0f172a; margin-bottom:4px;">🏷️ {_esc(group.market)}</div>
                <div style="font-size:11px; color:#475569; line-height:1.45; margin-bottom:6px;">{_esc(group.summary)}</div>
                <div style="display:flex; flex-wrap:wrap;">{company_pills}</div>
            </div>
            """)
        comp_html = "".join(comp_cards)

    # 5. 核心驱动力与长期趋势
    drivers = result.driver_insights or [IndustryChainInsight(title=d, detail="") for d in result.drivers]
    trends = result.trends or []
    drivers_html = ""
    if drivers:
        d_items = []
        for d in drivers:
            d_items.append(f"""
            <div style="margin-bottom:6px; font-size:11px; color:#334155; line-height:1.5;">
                <strong style="color:#0f172a;">• {_esc(d.title)}</strong>
                {f'<div style="color:#64748b; margin-left:12px; margin-top:2px;">{_esc(d.detail)}</div>' if d.detail else ""}
            </div>
            """)
        drivers_html = "".join(d_items)

    trends_html = ""
    if trends:
        t_items = []
        for tr in trends:
            t_items.append(f"""
            <div style="margin-bottom:6px; font-size:11px; color:#334155; line-height:1.5;">
                <strong style="color:#0f172a;">• {_esc(tr.title)}</strong>
                {f'<div style="color:#64748b; margin-left:12px; margin-top:2px;">{_esc(tr.detail)}</div>' if tr.detail else ""}
            </div>
            """)
        trends_html = "".join(t_items)

    # 6. 风险与制约因素
    risks = result.risk_insights or [IndustryChainInsight(title=r, detail="") for r in result.risks]
    risks_html = ""
    if risks:
        r_items = []
        for r in risks:
            r_items.append(f"""
            <div style="margin-bottom:6px; font-size:11px; color:#991b1b; line-height:1.5; background:#fef2f2; border:1px solid #fee2e2; border-radius:4px; padding:6px 10px;">
                <strong>⚠️ {_esc(r.title)}</strong>
                {f'<div style="color:#7f1d1d; margin-top:2px;">{_esc(r.detail)}</div>' if r.detail else ""}
            </div>
            """)
        risks_html = "".join(r_items)

    # 6.5 产业链传导与利润弹性机制
    relationships_rows_html = ""
    if result.relationships:
        direction_map = {
            "positive": ("正向传导", "#16a34a", "#f0fdf4"),
            "negative": ("负向传导", "#dc2626", "#fef2f2"),
            "mixed": ("双向波动", "#d97706", "#fffbeb"),
            "unknown": ("定性关联", "#475569", "#f8fafc"),
        }
        rel_map = {
            "supply": "供货配套",
            "purchase": "大客户采购",
            "substitute": "技术替代",
            "compete": "同业竞争",
            "transmission": "利润传导",
        }
        for r in result.relationships:
            dir_label, dir_fg, dir_bg = direction_map.get(
                r.impact_direction or "unknown", ("定性关联", "#475569", "#f8fafc")
            )
            rel_label = rel_map.get(r.relation_type, r.relation_type or "定性关联")
            dir_badge = f'<span style="display:inline-block; font-size:10px; color:{dir_fg}; background:{dir_bg}; border:1px solid {dir_fg}33; padding:1px 6px; border-radius:3px;">{dir_label}</span>'
            rel_badge = f'<span style="display:inline-block; font-size:10px; color:#0284c7; background:#e0f2fe; padding:1px 6px; border-radius:3px; margin-left:4px;">{rel_label}</span>'
            driver_info = (
                f'<div style="font-size:10px; color:#64748b; margin-top:2px;"><b>驱动冲击：</b>{_esc(r.driver)}</div>'
                if r.driver
                else ""
            )
            time_lag_info = (
                f'<div style="font-size:10px; color:#0284c7; margin-top:2px;"><b>传导滞后期：</b>{_esc(r.time_lag)}</div>'
                if r.time_lag
                else ""
            )
            metric_info = (
                f'<div style="font-size:10px; color:#0f766e; margin-top:2px;"><b>观测指标：</b>{_esc(r.target_metric)}</div>'
                if r.target_metric
                else ""
            )
            tracking_info = (
                f'<div style="font-size:10px; color:#475569; margin-top:2px;"><b>高频跟踪指标：</b>{_esc("、".join(r.tracking_metrics))}</div>'
                if r.tracking_metrics
                else ""
            )
            conditions_info = (
                f'<div style="font-size:10px; color:#475569; margin-top:2px;"><b>兑现条件：</b>{_esc("；".join(r.conditions))}</div>'
                if r.conditions
                else ""
            )
            invalidation_info = (
                f'<div style="font-size:10px; color:#b91c1c; margin-top:2px;"><b>失效风险：</b>{_esc(r.invalidation)}</div>'
                if r.invalidation
                else ""
            )
            evidence_tags = _render_evidence_tags(r.evidence_ids)

            relationships_rows_html += f"""
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:7px 10px; font-weight:700; color:#0f172a; font-size:11px; width:170px;">
                    {_esc(r.source_node)} → {_esc(r.target_node)}
                    <div style="margin-top:3px;">{dir_badge}{rel_badge}</div>
                </td>
                <td style="padding:7px 10px; font-size:11px; color:#334155; line-height:1.45;">
                    <div>{_esc(r.detail or r.title)}</div>
                    {driver_info}
                    {time_lag_info}
                    {metric_info}
                    {tracking_info}
                    {conditions_info}
                    {invalidation_info}
                </td>
                <td style="padding:7px 10px; width:90px; text-align:right;">
                    <div>{evidence_tags}</div>
                </td>
            </tr>
            """

    # 7. 重点股票标的
    relevance_map = {
        "earnings": ("业绩兑现", "#16a34a", "#f0fdf4"),
        "business": ("实质业务", "#0284c7", "#e0f2fe"),
        "concept": ("概念布局", "#d97706", "#fffbeb"),
        "unverified": ("待验证", "#64748b", "#f1f5f9"),
    }
    stocks_rows_html = ""
    if result.key_stocks:
        for s in result.key_stocks:
            stock_code = _esc(s.code or "--")
            stock_name = _esc(s.name or s.company or "--")
            role_desc = _esc(s.role or s.description or "--")
            source_badge = _render_source_badge(s.source, s.source_url)
            evidence_tags = _render_evidence_tags(s.evidence_ids)

            rel_text, rel_fg, rel_bg = relevance_map.get(s.business_relevance, ("待验证", "#64748b", "#f1f5f9"))
            rel_badge = f'<span style="display:inline-block; font-size:9.5px; color:{rel_fg}; background:{rel_bg}; border:1px solid {rel_fg}33; padding:1px 5px; border-radius:3px; margin-top:2px;">{rel_text}</span>'

            val_parts = []
            if s.total_market_cap:
                val_parts.append(f"总市值: {_esc(s.total_market_cap)}")
            if s.pe:
                val_parts.append(f"PE: {_esc(s.pe)}")
            if s.pb:
                val_parts.append(f"PB: {_esc(s.pb)}")
            val_html = (
                f'<div style="font-size:10px; color:#475569; line-height:1.35;">{"<br>".join(val_parts)}</div>'
                if val_parts
                else '<span style="color:#94a3b8; font-size:10px;">--</span>'
            )

            rev_info = (
                f'<span style="display:inline-block; font-size:9.5px; color:#0284c7; background:#e0f2fe; padding:1px 5px; border-radius:3px; margin-left:4px;">业务占比: {_esc(s.revenue_share)}</span>'
                if s.revenue_share
                else ""
            )

            stocks_rows_html += f"""
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:6px 10px; font-weight:700; color:#0284c7; font-size:11px; width:75px;">{stock_code}</td>
                <td style="padding:6px 10px; font-weight:700; color:#0f172a; font-size:11px; width:115px;">
                    <div>{stock_name}</div>
                    <div>{rel_badge}</div>
                </td>
                <td style="padding:6px 10px; font-size:10px; width:100px;">{val_html}</td>
                <td style="padding:6px 10px; font-size:11px; color:#334155;">
                    <div>{role_desc} {rev_info}</div>
                </td>
                <td style="padding:6px 10px; width:110px; text-align:right;">
                    <div>{source_badge}</div>
                    <div>{evidence_tags}</div>
                </td>
            </tr>
            """

    # 8. 关键产业事件
    events_html = ""
    if result.key_events:
        e_cards = []
        for ev in result.key_events:
            date_badge = f'<span style="font-size:10px; font-weight:700; color:#0284c7; background:#e0f2fe; padding:2px 6px; border-radius:4px; margin-right:6px;">{_esc(ev.date or "近期")}</span>'
            source_badge = _render_source_badge(ev.source, ev.source_url)
            e_cards.append(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px; margin-bottom:6px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <div>{date_badge}<strong style="font-size:11px; color:#0f172a;">{_esc(ev.title)}</strong></div>
                    {source_badge}
                </div>
                {f'<div style="font-size:11px; color:#475569; line-height:1.45;">• 影响研判: {_esc(ev.impact)}</div>' if ev.impact else ""}
            </div>
            """)
        events_html = "".join(e_cards)

    # 9. 证据审计与信息源
    sources_html = ""
    if result.sources:
        s_items = []
        for src in result.sources:
            safe_u = _safe_url(src.url)
            title_node = (
                f'<a href="{safe_u}" target="_blank" style="color:#0284c7; text-decoration:none; font-weight:600;">{_esc(src.title)} ↗</a>'
                if safe_u
                else f'<strong style="color:#334155;">{_esc(src.title)}</strong>'
            )
            meta_str = (
                f"({_esc(src.publisher or '权威机构')} · {_esc(src.date or '')})" if src.publisher or src.date else ""
            )
            s_items.append(
                f'<div style="margin-bottom:4px; font-size:10px; color:#64748b;">• {title_node} <span style="color:#94a3b8;">{meta_str}</span></div>'
            )
        sources_html = "".join(s_items)

    missing_html = ""
    if result.missing_evidence:
        m_items = "".join(f'<li style="margin-bottom:2px;">{_esc(it)}</li>' for it in result.missing_evidence)
        missing_html = f'<div style="background:#fffbeb; border:1px solid #fef3c7; border-radius:6px; padding:8px 10px; margin-top:8px;"><strong style="font-size:11px; color:#92400e;">⚠️ 待核验数据缺口：</strong><ul style="margin:4px 0 0 16px; font-size:10px; color:#78350f;">{m_items}</ul></div>'

    conflicts_html = ""
    if result.conflicts:
        c_items = "".join(
            f'<div style="margin-bottom:4px;"><strong>{_esc(c.topic)}</strong>: {_esc(" vs ".join(c.values))} ({_esc(c.reason)})</div>'
            for c in result.conflicts
        )
        conflicts_html = f'<div style="background:#fef2f2; border:1px solid #fee2e2; border-radius:6px; padding:8px 10px; margin-top:8px;"><strong style="font-size:11px; color:#991b1b;">⚡ 冲突口径比对：</strong><div style="margin-top:4px; font-size:10px; color:#7f1d1d;">{c_items}</div></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{_esc(name)} 产业链深度研究报告</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            color: #0f172a;
            background: #ffffff;
            margin: 0;
            padding: 0;
            line-height: 1.5;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        .header-card {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #ffffff;
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }}
        .header-title {{
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .section-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 14px;
            page-break-inside: avoid;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 700;
            color: #0f172a;
            border-bottom: 1.5px solid #e2e8f0;
            padding-bottom: 6px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .chain-section {{
            page-break-inside: auto;
        }}
        .panorama-block {{
            background: #ffffff;
            border: 1px solid #dbe4f0;
            border-radius: 8px;
            padding: 10px 12px 4px;
            margin-bottom: 12px;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .panorama-heading {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 4px;
            color: #0f172a;
            font-size: 12px;
        }}
        .panorama-heading strong {{
            display: block;
            font-size: 13px;
        }}
        .panorama-heading span {{
            color: #64748b;
            font-size: 10px;
        }}
        .panorama-legend {{
            display: flex;
            align-items: center;
            gap: 4px;
            color: #64748b;
            font-size: 9px;
        }}
        .panorama-legend i {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            display: inline-block;
            margin-left: 5px;
        }}
        .upstream-dot {{ background: #0284c7; }}
        .midstream-dot {{ background: #16a34a; }}
        .downstream-dot {{ background: #d97706; }}
        .panorama-block svg {{
            display: block;
            width: 100%;
            height: auto;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            overflow: hidden;
            page-break-inside: auto;
        }}
        tr {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        thead {{
            display: table-header-group;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            font-size: 11px;
            font-weight: 700;
            padding: 6px 10px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        .toc-bar {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px 12px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 7px 12px;
            margin-bottom: 14px;
            font-size: 10.5px;
            color: #64748b;
            page-break-inside: avoid;
        }}
        .toc-title {{
            font-weight: 700;
            color: #0f172a;
            margin-right: 2px;
        }}
        .toc-item {{
            color: #2563eb;
            font-weight: 500;
        }}
        .disclaimer-box {{
            background: #f8fafc;
            border: 1px dashed #cbd5e1;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 9px;
            color: #64748b;
            line-height: 1.5;
            margin-top: 16px;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>

    <!-- 顶部封面 Header -->
    <div class="header-card">
        <div class="header-title">
            <span>🌐 {_esc(name)} 产业链深度研究报告</span>
            <span style="font-size:12px; font-weight:600; padding:3px 10px; border-radius:4px; background:{quality_bg}; color:{quality_fg};">
                {quality_label}
            </span>
        </div>
        <div style="font-size:12px; color:#94a3b8; margin-bottom:10px;">
            别名/关联赛道：{_esc(aliases_str or "主流细分领域")} ｜ 研究范围：{scope_region} · {scope_company} ｜ 研判周期：{date_range}
        </div>
        <div style="display:flex; gap:16px; font-size:11px; color:#cbd5e1; border-top:1px solid #334155; padding-top:8px;">
            <div>📌 证据引用: <strong style="color:#ffffff;">{stats.selected_count}</strong> 条权威事实</div>
            <div>📊 核心维度覆盖率: <strong style="color:#ffffff;">{coverage_percent}%</strong></div>
            <div>⚡ 知识库状态: <strong style="color:#ffffff;">{result.archive_id or "最新实时生成"}</strong></div>
        </div>
    </div>

    <!-- 报告目录导航 TOC -->
    <div class="toc-bar">
        <span class="toc-title">📑 报告目录</span>
        <span class="toc-item">01 战略定位与概述</span>
        <span>•</span>
        <span class="toc-item">02 产业链图谱与环节</span>
        <span>•</span>
        <span class="toc-item">03 技术路线与竞争</span>
        <span>•</span>
        <span class="toc-item">04 增长驱动与风险</span>
        <span>•</span>
        <span class="toc-item">05 传导机制与弹性</span>
        <span>•</span>
        <span class="toc-item">06 核心关注标的</span>
        <span>•</span>
        <span class="toc-item">07 重大产业事件</span>
        <span>•</span>
        <span class="toc-item">08 证据审计与信息源</span>
    </div>

    <!-- 01 战略定位与产业全景概述 -->
    <div class="section-card">
        <div class="section-title">01 · 战略定位与产业全景概述</div>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:8px;">
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="font-size:11px; font-weight:700; color:#0284c7; margin-bottom:4px;">🎯 战略定位与产业地位</div>
                <div style="font-size:11px; color:#334155; line-height:1.5;">{_esc(positioning)}</div>
            </div>
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="font-size:11px; font-weight:700; color:#16a34a; margin-bottom:4px;">📋 核心产业概述与投资结论</div>
                <div style="font-size:11px; color:#334155; line-height:1.5;">{_esc(summary)}</div>
            </div>
        </div>
        {metrics_cards_html}
    </div>

    <!-- 02 产业链上下游全景与价值链分配 -->
    <div class="section-card chain-section">
        <div class="section-title">02 · 产业链上下游全景环节与代表厂商</div>
        {panorama_html}
        <table>
            <thead>
                <tr>
                    <th>产业链环节</th>
                    <th>核心环节/节点</th>
                    <th>角色定位与技术门槛</th>
                    <th>代表厂商与市场份额</th>
                    <th style="text-align:right;">信息源/证据</th>
                </tr>
            </thead>
            <tbody>
                {chain_rows_html or '<tr><td colspan="5" style="text-align:center; padding:12px; color:#94a3b8; font-size:11px;">暂无上下游结构化数据</td></tr>'}
            </tbody>
        </table>
    </div>

    <!-- 03 核心技术路线与竞争格局 -->
    <div class="section-card">
        <div class="section-title">03 · 核心技术路线演进与市场竞争格局</div>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
            <div>
                <div style="font-size:12px; font-weight:700; color:#475569; margin-bottom:6px;">🔬 主流技术路线对比与商业化成熟度</div>
                {tech_html or '<div style="color:#94a3b8; font-size:11px;">暂无技术路线明细</div>'}
            </div>
            <div>
                <div style="font-size:12px; font-weight:700; color:#475569; margin-bottom:6px;">🏆 市场梯队、集中度与竞争阵营</div>
                {comp_html or '<div style="color:#94a3b8; font-size:11px;">暂无竞争格局明细</div>'}
            </div>
        </div>
    </div>

    <!-- 04 增长驱动、长期趋势与瓶颈风险 -->
    <div class="section-card">
        <div class="section-title">04 · 产业增长驱动力、演进趋势与核心风险</div>
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px;">
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="font-size:12px; font-weight:700; color:#16a34a; margin-bottom:6px;">🚀 核心增长驱动力</div>
                {drivers_html or '<div style="color:#94a3b8; font-size:11px;">暂无驱动力数据</div>'}
            </div>
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="font-size:12px; font-weight:700; color:#0284c7; margin-bottom:6px;">📈 产业长期演进趋势</div>
                {trends_html or '<div style="color:#94a3b8; font-size:11px;">暂无趋势数据</div>'}
            </div>
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                <div style="font-size:12px; font-weight:700; color:#dc2626; margin-bottom:6px;">⚠️ 核心风险与瓶颈制约</div>
                {risks_html or '<div style="color:#94a3b8; font-size:11px;">暂无风险数据</div>'}
            </div>
        </div>
    </div>

    <!-- 05 产业链传导机制与利润弹性 -->
    <div class="section-card">
        <div class="section-title">05 · 产业链传导机制与利润弹性假定</div>
        <table>
            <thead>
                <tr>
                    <th>传导链路与类型</th>
                    <th>传导机制、成立条件与失效风险</th>
                    <th style="text-align:right;">核验状态/证据</th>
                </tr>
            </thead>
            <tbody>
                {relationships_rows_html or '<tr><td colspan="3" style="text-align:center; padding:12px; color:#94a3b8; font-size:11px;">暂无明确传导关系结构化数据</td></tr>'}
            </tbody>
        </table>
    </div>

    <!-- 06 重点上市公司标的映射 -->
    <div class="section-card">
        <div class="section-title">06 · 核心关注标的与产业链映射</div>
        <table>
            <thead>
                <tr>
                    <th>证券代码</th>
                    <th>标的名称 / 业务关联</th>
                    <th>当前估值 / 市值</th>
                    <th>产业链环节角色、核心壁垒与弹性看点</th>
                    <th style="text-align:right;">来源/证据</th>
                </tr>
            </thead>
            <tbody>
                {stocks_rows_html or '<tr><td colspan="5" style="text-align:center; padding:12px; color:#94a3b8; font-size:11px;">暂无核心关注标的明细</td></tr>'}
            </tbody>
        </table>
    </div>

    <!-- 07 重大产业事件与催化剂 -->
    <div class="section-card">
        <div class="section-title">07 · 重大产业事件与催化剂跟踪</div>
        {events_html or '<div style="color:#94a3b8; font-size:11px;">暂无重大事件记录</div>'}
    </div>

    <!-- 08 证据链审计与权威信息源 -->
    <div class="section-card">
        <div class="section-title">08 · 证据链审计、权威信息源与数据缺口</div>
        <div style="display:grid; grid-template-columns: 1.2fr 1fr; gap:12px;">
            <div>
                <div style="font-size:11px; font-weight:700; color:#475569; margin-bottom:6px;">📚 权威信息源与研报清单</div>
                {sources_html or '<div style="color:#94a3b8; font-size:10px;">暂无引用的公开来源</div>'}
            </div>
            <div>
                <div style="font-size:11px; font-weight:700; color:#475569; margin-bottom:6px;">🔍 审慎核验与数据缺口</div>
                {missing_html}
                {conflicts_html}
            </div>
        </div>
    </div>

    <!-- 研报合规免责声明 -->
    <div class="disclaimer-box">
        <strong>【研究声明与免责提示】</strong><br>
        1. 本报告由 A股智能投研体系（AI Agentic Financial Platform）基于全市场公开产业研报、上市公司公告及大数据挖掘引擎自动构建，旨在为行业分析师与专业投资者提供结构化产业链全景参考，不构成针对任何具体股票或资产的投资招揽或保证。<br>
        2. 产业技术路线迭代迅速、政策与地缘环境具有多变性，请结合一手渠道持续跟踪各环节核心企业经营与订单情况。
    </div>

</body>
</html>
"""


async def render_industry_chain_pdf_bytes(html_content: str) -> bytes:
    """通过共享的有界 Chromium 队列渲染报告，保留既有页眉页脚和 A4 布局。"""
    return await render_pdf(
        html_content,
        header_template='<div style="font-size:8px; width:100%; text-align:right; color:#94a3b8; padding-right:14mm; font-family:sans-serif;">A股智能投研体系 · 产业链深度研究报告</div>',
        footer_template='<div style="font-size:8px; width:100%; display:flex; justify-content:space-between; color:#94a3b8; padding:0 14mm; font-family:sans-serif;"><span>内部研究参考 · 不构成直接投资建议</span><span>第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页</span></div>',
    )
