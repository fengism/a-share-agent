"""Deterministically render validated industry-chain structures as GFM Markdown."""

from __future__ import annotations

from app.core.urls import safe_http_url
from app.modules.industry_chain.models import (
    IndustryChainConflict,
    IndustryChainInsight,
    IndustryChainNode,
    IndustryChainResult,
)
from app.modules.industry_chain.presentation import presentation_payload


def _escape_table(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _source(source: str, url: str) -> str:
    safe_url = safe_http_url(url)
    if safe_url:
        return f"[{source or '原文'}]({safe_url})"
    return source or ""


def _claim_label(item: IndustryChainInsight) -> str:
    claim = (
        "机构预测"
        if item.evidence_basis == "forecast"
        else {"fact": "事实陈述", "inference": "推断", "opinion": "观点"}[item.claim_type]
    )
    confidence = {"high": "高", "medium": "中", "low": "低"}[item.confidence]
    return f"{claim} · 置信度：{confidence}"


def _insights(title: str, items: list[IndustryChainInsight]) -> list[str]:
    lines = [title]
    if not items:
        return [*lines, "暂无可靠结构化证据。", ""]
    for item in items:
        src = _source(item.source, item.source_url)
        details = [item.detail, item.evidence, f"来源：{src}" if src else ""]
        suffix = "；".join(value for value in details if value)
        lines.append(f"- **{item.title}**（{_claim_label(item)}）{f'：{suffix}' if suffix else ''}")
    lines.append("")
    return lines


def _node_name(node: IndustryChainNode) -> str:
    return str(node.name or node.company or node.code or "未命名环节")


def _chain_table(result: IndustryChainResult) -> list[str]:
    rows = []
    for stage, nodes in (("上游", result.upstream), ("中游", result.midstream), ("下游", result.downstream)):
        for node in nodes:
            companies = "、".join(node.companies) or (node.code or "-")
            source = _source(node.source, node.source_url)
            share = f"（份额: {node.market_share}）" if node.market_share else ""
            rows.append(
                [
                    stage,
                    _node_name(node),
                    node.role or node.description or "-",
                    f"{companies}{share}",
                    source or "-",
                ]
            )
    lines = ["## 5. 上下游关系与核心环节"]
    if not rows:
        return [*lines, "暂无可靠结构化证据。", ""]
    lines.extend(
        [
            "| 环节 | 节点名称 | 核心角色与职能 | 代表公司/标的 | 来源参考 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    lines.extend("| " + " | ".join(_escape_table(value) for value in row) + " |" for row in rows)
    lines.append("")

    if result.relationships:
        lines.append("### 环节间传导机制与核心假设")
        for edge in result.relationships:
            direction_badge = (
                "正向传导"
                if edge.impact_direction == "positive"
                else "负向传导"
                if edge.impact_direction == "negative"
                else "条件传导"
            )
            lines.extend(
                [
                    f"#### {edge.source_node} → {edge.target_node}（{direction_badge}）",
                    f"- **驱动冲击**：{edge.driver or '待补证'}",
                    f"- **传导机制**：{edge.detail or edge.title}",
                    f"- **观测/经营指标**：{edge.target_metric or '待补证'}",
                    f"- **成立条件**：{'；'.join(edge.conditions) or '待补证'}",
                    f"- **传导时滞**：{edge.time_lag or '非即时兑现'}",
                    f"- **失效风险**：{edge.invalidation or '待补证'}",
                ]
            )
            if edge.tracking_metrics:
                lines.append(f"- **高频跟踪指标**：{'；'.join(edge.tracking_metrics)}")
            if edge.citations:
                lines.extend(f"> 引用根据：{c.quote} {_source('原文', c.source_url)}" for c in edge.citations if c.quote)
            lines.append("")
    return lines


def _market_table(result: IndustryChainResult) -> list[str]:
    lines = ["## 2. 市场规模与增长"]
    if not result.market_metrics:
        return [*lines, "暂无可靠结构化证据。", ""]
    lines.extend(
        [
            "| 指标名称 | 数值/规模 | 统计期间 | 增速/趋势 | 验证状态 | 来源参考 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in result.market_metrics:
        status_label = (
            "机构预测"
            if item.evidence_basis == "forecast"
            else "已匹配原文"
            if item.verification_status == "quote_matched"
            else "待复核"
        )
        row = [
            item.label,
            item.value,
            item.period or "-",
            item.growth or "-",
            status_label,
            _source(item.source, item.source_url) or "-",
        ]
        lines.append("| " + " | ".join(_escape_table(value) for value in row) + " |")
    lines.append("")
    return lines


def _competition(result: IndustryChainResult) -> list[str]:
    lines = ["## 3. 全球与中国竞争格局"]
    if not result.competition:
        return [*lines, "暂无可靠结构化证据。", ""]
    for group in result.competition:
        lines.append(f"### {group.market}")
        if group.summary:
            lines.append(group.summary)
        for company in group.companies:
            src = _source(company.source, company.source_url)
            details = [
                company.role,
                f"市场份额：{company.market_share}" if company.market_share else "",
                f"来源：{src}" if src else "",
            ]
            suffix = "；".join(value for value in details if value)
            lines.append(f"- **{_node_name(company)}**{f'：{suffix}' if suffix else ''}")
    lines.append("")
    return lines


def _events(result: IndustryChainResult) -> list[str]:
    lines = ["## 7. 资本运作与关键事件"]
    lines.extend(_insights("### 资本运作与产业动作", result.capital_moves)[1:])
    if result.key_events:
        lines.append("### 行业关键事件")
        for event in result.key_events:
            src = _source(event.source, event.source_url)
            details = [event.impact, f"来源：{src}" if src else ""]
            suffix = "；".join(value for value in details if value)
            lines.append(f"- **{event.date or '近期'}｜{event.title}**{f'：{suffix}' if suffix else ''}")
        lines.append("")
    return lines


def _companies(result: IndustryChainResult) -> list[str]:
    company_title = (
        "重点公司及关注逻辑" if result.research_scope.get("company_scope") == "all_public" else "A 股重点公司及关注逻辑"
    )
    lines = [f"## 8. {company_title}"]
    if not result.key_stocks:
        return [*lines, "暂无可靠结构化证据。", ""]

    relevance_map = {
        "unverified": "待验证",
        "concept": "概念布局",
        "business": "业务深度相关",
        "earnings": "核心业绩贡献",
    }

    for company in result.key_stocks:
        name = _node_name(company)
        code_str = f" ({company.code})" if company.code else ""
        val_tags = []
        if company.total_market_cap:
            val_tags.append(f"总市值: {company.total_market_cap}")
        if company.price_change:
            val_tags.append(f"现价: {company.price_change}")
        if company.pe:
            pe_tag = f"PE(动): {company.pe}"
            if company.pe_percentile:
                pe_tag += f" [{company.pe_percentile}]"
            val_tags.append(pe_tag)
        if company.pb:
            val_tags.append(f"PB: {company.pb}")
        val_suffix = f" ｜ {' · '.join(val_tags)}" if val_tags else ""
        rel_label = relevance_map.get(company.business_relevance, "")
        rel_str = f"【{rel_label}】" if rel_label else ""

        lines.append(f"### {name}{code_str}{rel_str}{val_suffix}")
        if company.role or company.description:
            lines.append(f"- **业务定位**：{company.role or company.description}")
        if company.consensus_forecast:
            lines.append(f"- **机构一致预期**：{company.consensus_forecast}")
        if company.revenue_share:
            rev_period = f"（{company.revenue_period}）" if company.revenue_period else ""
            lines.append(f"- **相关业务占比**：{company.revenue_share} {rev_period}")
        if getattr(company, "overseas_share", ""):
            lines.append(f"- **出海与海外敞口**：{company.overseas_share}")
        if company.benefit_path:
            lines.append(f"- **核心受益逻辑**：{company.benefit_path}")
        if company.gross_margin or company.net_margin:
            margin_parts = []
            if company.gross_margin:
                margin_parts.append(f"毛利率：{company.gross_margin}")
            if company.net_margin:
                margin_parts.append(f"净利率：{company.net_margin}")
            lines.append(f"- **盈利水平**：{' ｜ '.join(margin_parts)}")
        if company.roe or company.growth_rate:
            perf_parts = []
            if company.roe:
                perf_parts.append(f"ROE：{company.roe}")
            if company.growth_rate:
                perf_parts.append(f"业绩增速：{company.growth_rate}")
            lines.append(f"- **资本回报与成长**：{' ｜ '.join(perf_parts)}")
        if company.moat:
            lines.append(f"- **核心壁垒与护城河**：{company.moat}")
        if company.eps_elasticity:
            lines.append(f"- **业绩/利润弹性看点**：{company.eps_elasticity}")
        if company.restricted_risk:
            lines.append(f"- **限售解禁监控**：{company.restricted_risk}")
        if company.metric:
            lines.append(f"- **经营跟踪指标**：{company.metric}")
        if company.realization_conditions:
            lines.append(f"- **兑现条件**：{'；'.join(company.realization_conditions)}")
        if company.invalidation_conditions:
            lines.append(f"- **失效风险**：{'；'.join(company.invalidation_conditions)}")
        if company.source or company.source_url:
            lines.append(f"- **资料参考**：{_source(company.source or '公司公告/官方研报', company.source_url)}")
        lines.append("")
    return lines


def _conflicts(conflicts: list[IndustryChainConflict]) -> list[str]:
    if not conflicts:
        return []
    lines = ["### 数据口径冲突说明"]
    for item in conflicts:
        values = " / ".join(item.values)
        details = "；".join(value for value in (values, item.reason) if value)
        lines.append(f"- **{item.topic}**{f'：{details}' if details else ''}")
    return [*lines, ""]


def _value_distribution_table(result: IndustryChainResult) -> list[str]:
    if not result.value_distribution:
        return []
    lines = ["### 产业链价值量（BOM）与利润池分布"]
    lines.extend(
        [
            "| 环节/核心组件 | BOM成本占比/价值量 | 毛利率区间 | 利润池占比 | 议价定价权 | 价值与竞争机制 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    power_map = {
        "high": "强（具备主导权）",
        "medium": "中（相对均衡）",
        "low": "弱（受上下游挤压）",
        "unverified": "待验证",
    }
    for item in result.value_distribution:
        p_label = power_map.get(item.pricing_power, item.pricing_power or "-")
        row = [
            item.segment,
            item.cost_share or "-",
            item.gross_margin_range or "-",
            item.profit_share or "-",
            p_label,
            item.detail or "-",
        ]
        lines.append("| " + " | ".join(_escape_table(v) for v in row) + " |")
    lines.append("")
    return lines


def _cycle_analysis_section(result: IndustryChainResult) -> list[str]:
    c = result.cycle_analysis
    if not any((c.stage, c.capacity_utilization, c.expansion_lead_time, c.inflection_point, c.pass_through_ability)):
        return []
    lines = ["### 供需格局、周期定位与成本顺价机制"]
    if c.stage:
        lines.append(f"- **周期所处阶段**：{c.stage}")
    if c.capacity_utilization:
        lines.append(f"- **行业有效产能/开工率**：{c.capacity_utilization}")
    if c.expansion_lead_time:
        lines.append(f"- **扩产与认证壁垒周期**：{c.expansion_lead_time}")
    if c.inflection_point:
        lines.append(f"- **供需平衡与景气拐点推演**：{c.inflection_point}")
    if c.pass_through_ability:
        lines.append(f"- **成本顺价能力与毛利弹性**：{c.pass_through_ability}")
    lines.append("")
    return lines


def _expectation_divergence_section(result: IndustryChainResult) -> list[str]:
    if not result.expectation_divergences:
        return []
    lines = ["### 市场一致预期 vs 本次研究分歧（预期差推演）"]
    for item in result.expectation_divergences:
        lines.extend(
            [
                f"#### 分歧焦点：{item.topic}",
                f"- **市场一致预期**：{item.consensus or '广泛乐观或悲观定价'}",
                f"- **本次审慎推断**：{item.divergence}",
                f"- **预期差验证窗口/核心催化**：{item.catalyst_trigger or '待跟踪后续季度披露'}",
                "",
            ]
        )
    return lines


def render_industry_markdown(result: IndustryChainResult) -> str:
    result = IndustryChainResult.model_validate(presentation_payload(result))
    lines = [f"# {result.name or '产业'}产业链分析报告", ""]
    scope = result.research_scope
    if scope:
        scope_values = [
            scope.get("region", ""),
            " 至 ".join(value for value in (scope.get("start_date", ""), scope.get("end_date", "")) if value),
            scope.get("company_scope", ""),
        ]
        lines.extend([f"> 研究范围：{' · '.join(value for value in scope_values if value)}", ""])

    lines.extend(["> 风险提示：本研报基于公开市场数据及分析模型综合生成，所载内容不构成直接投资买卖建议。", ""])
    lines.extend(["## 1. 行业定位与核心结论", result.summary or "暂无可靠核心结论。"])
    if result.positioning:
        lines.extend(["", f"**产业定位：** {result.positioning}"])

    lines.extend(_value_distribution_table(result))
    lines.extend(_cycle_analysis_section(result))
    lines.extend(_expectation_divergence_section(result))

    if result.research_theses:
        lines.append("")
        lines.append("### 核心投资逻辑与推演")
        for thesis in result.research_theses:
            verification_note = "原文前提片段已匹配" if thesis.verification_status == "quote_matched" else "前提待验证"
            lines.extend(
                [
                    f"#### {thesis.title}",
                    thesis.detail,
                    f"- **推演状态**：{verification_note}",
                    f"- **上下游路径**：{' → '.join(thesis.chain_path) or '跨环节传导'}",
                    f"- **传导机制**：{thesis.mechanism or '待补充'}",
                    f"- **成立条件**：{'；'.join(thesis.conditions) or '待补充'}",
                    f"- **跟踪指标**：{'；'.join(thesis.tracking_metrics) or '待补充'}",
                    f"- **失效条件**：{thesis.invalidation or '待补充'}",
                ]
            )
            if thesis.counter_evidence:
                lines.append(f"- **反向事实/潜在阻力**：{thesis.counter_evidence}")
            if thesis.citations:
                lines.extend(f"> 论据摘录：{citation.quote} {_source('原文', citation.source_url)}" for citation in thesis.citations if citation.quote)
            lines.append("")

    if result.verification_repair.attempted_rounds and result.verification_repair.note:
        lines.append(f"> 审校说明：{result.verification_repair.note}\n")

    lines.extend(_market_table(result))
    lines.extend(_competition(result))
    lines.extend(_insights("## 4. 技术路线、商业模式与壁垒", result.technology_routes))
    lines.extend(_chain_table(result))
    lines.extend(_insights("## 6. 关键驱动与催化剂", [*result.driver_insights, *result.trends]))
    lines.extend(_events(result))
    lines.extend(_companies(result))
    lines.extend(_insights("## 9. 投资风险提示", result.risk_insights))

    lines.append("## 附录：数据来源与口径说明")
    if result.sources:
        for source in result.sources:
            label = _source(source.title, source.url) or source.title
            metadata = " · ".join(value for value in (source.publisher, source.date) if value)
            suffix = f"（{metadata}）" if metadata else ""
            lines.append(f"- {label}{suffix}")
    else:
        lines.append("- 依据全市场公开披露、行业统计及主流投研研报综合整理。")

    if result.missing_evidence:
        lines.append("")
        lines.append("### 需进一步跟踪与核验事项")
        lines.extend(f"- {item}" for item in result.missing_evidence)

    lines.extend(_conflicts(result.conflicts))
    return "\n".join(lines).strip() + "\n"

