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


def _evidence(ids: list[str]) -> str:
    return "、".join(dict.fromkeys(ids)) if ids else ""


def _source(source: str, url: str) -> str:
    safe_url = safe_http_url(url)
    if safe_url:
        return f"[{source or '原文'}]({safe_url})"
    return source


def _claim_label(item: IndustryChainInsight) -> str:
    claim = (
        "机构预测"
        if item.evidence_basis == "forecast"
        else {"fact": "事实陈述", "inference": "推断", "opinion": "观点"}[item.claim_type]
    )
    confidence = {"high": "高", "medium": "中", "low": "低"}[item.confidence]
    return f"{claim}｜置信度：{confidence}"


def _insights(title: str, items: list[IndustryChainInsight]) -> list[str]:
    lines = [title]
    if not items:
        return [*lines, "暂无可靠结构化证据。", ""]
    for item in items:
        details = [item.detail, item.evidence, _source(item.source, item.source_url), _evidence(item.evidence_ids)]
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
            companies = "、".join(node.companies)
            source = _source(node.source, node.source_url)
            rows.append(
                [
                    stage,
                    _node_name(node),
                    node.role or node.description,
                    companies,
                    source,
                    _evidence(node.evidence_ids),
                ]
            )
    lines = ["## 5. 上下游关系与价值分配"]
    if not rows:
        return [*lines, "暂无可靠结构化证据。", ""]
    lines.extend(
        [
            "| 环节 | 节点 | 角色/说明 | 相关公司 | 来源 | 资料索引 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    lines.extend("| " + " | ".join(_escape_table(value) for value in row) + " |" for row in rows)
    lines.append("")
    return lines


def _market_table(result: IndustryChainResult) -> list[str]:
    lines = ["## 2. 市场规模与增长"]
    if not result.market_metrics:
        return [*lines, "暂无可靠结构化证据。", ""]
    lines.extend(
        [
            "| 指标 | 数据 | 期间 | 增长 | 来源 | 资料索引 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in result.market_metrics:
        row = [
            item.label,
            item.value
            + ("（机构预测）" if item.evidence_basis == "forecast" else "")
            + ("（待验证）" if item.verification_status != "quote_matched" else "（原文匹配，非事实核实）"),
            item.period,
            item.growth,
            _source(item.source, item.source_url),
            _evidence(item.evidence_ids),
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
            details = [
                company.role,
                company.market_share,
                _source(company.source, company.source_url),
                _evidence(company.evidence_ids),
            ]
            suffix = "；".join(value for value in details if value)
            lines.append(f"- **{_node_name(company)}**{f'：{suffix}' if suffix else ''}")
    lines.append("")
    return lines


def _events(result: IndustryChainResult) -> list[str]:
    lines = ["## 7. 资本运作与关键事件"]
    lines.extend(_insights("### 资本运作与产业动作", result.capital_moves)[1:])
    if result.key_events:
        lines.append("### 关键事件")
        for event in result.key_events:
            details = [event.impact, _source(event.source, event.source_url), _evidence(event.evidence_ids)]
            suffix = "；".join(value for value in details if value)
            lines.append(f"- **{event.date or '时间待确认'}｜{event.title}**{f'：{suffix}' if suffix else ''}")
        lines.append("")
    return lines


def _companies(result: IndustryChainResult) -> list[str]:
    company_title = (
        "重点公司及关注逻辑" if result.research_scope.get("company_scope") == "all_public" else "A 股重点公司及关注逻辑"
    )
    lines = [f"## 8. {company_title}"]
    if not result.key_stocks:
        return [*lines, "暂无可靠结构化证据。", ""]
    for company in result.key_stocks:
        identity = " ".join(value for value in (_node_name(company), company.code or "") if value)
        details = [
            company.role,
            company.description,
            company.metric,
            _source(company.source, company.source_url),
            _evidence(company.evidence_ids),
        ]
        suffix = "；".join(value for value in details if value)
        lines.append(f"- **{identity}**{f'：{suffix}' if suffix else ''}")
    lines.append("")
    return lines


def _conflicts(conflicts: list[IndustryChainConflict]) -> list[str]:
    if not conflicts:
        return []
    lines = ["### 数据口径冲突"]
    for item in conflicts:
        values = " / ".join(item.values)
        details = "；".join(value for value in (values, item.reason, _evidence(item.evidence_ids)) if value)
        lines.append(f"- **{item.topic}**{f'：{details}' if details else ''}")
    return [*lines, ""]


def render_industry_markdown(result: IndustryChainResult) -> str:
    result = IndustryChainResult.model_validate(presentation_payload(result))
    lines = [f"# {result.name or '产业'}产业链分析", ""]
    scope = result.research_scope
    if scope:
        scope_values = [
            scope.get("region", ""),
            " 至 ".join(value for value in (scope.get("start_date", ""), scope.get("end_date", "")) if value),
            scope.get("company_scope", ""),
        ]
        lines.extend([f"> 研究范围：{' · '.join(value for value in scope_values if value)}", ""])

    lines.extend(["> 资料完整度不代表投资价值；原文匹配不等于事实核实，待验证内容不得作为确定性结论。", ""])
    lines.extend(["## 1. 行业定位与核心结论", result.summary or "暂无可靠核心结论。"])
    if result.research_theses:
        lines.append("### 核心研究判断（推断不等于已发生事实）")
        for thesis in result.research_theses:
            lines.extend(
                [
                    f"#### {thesis.title}",
                    thesis.detail,
                    f"证据状态：{'原文前提片段已匹配，推导仍需复核' if thesis.verification_status == 'quote_matched' else '缺少匹配前提，待验证'}",
                    f"上下游路径：{' → '.join(thesis.chain_path) or '尚未建立有向跨环节路径'}",
                    f"传导机制：{thesis.mechanism}",
                    f"成立条件：{'；'.join(thesis.conditions) or '待补充'}",
                    f"反向证据：{thesis.counter_evidence or '本次未取得反向证据'}",
                    f"失效条件：{thesis.invalidation or '待补充'}",
                    f"跟踪指标：{'；'.join(thesis.tracking_metrics) or '待补充'}",
                ]
            )
            lines.extend(f"> {citation.quote} {_source('原文', citation.source_url)}" for citation in thesis.citations)
    if result.verification_repair.attempted_rounds:
        lines.append(f"补证说明：{result.verification_repair.note}")

    if result.summary_evidence_ids:
        lines.append(_evidence(result.summary_evidence_ids))
    if result.positioning:
        lines.extend(["", f"**产业定位：** {result.positioning}"])
        if result.positioning_evidence_ids:
            lines.append(_evidence(result.positioning_evidence_ids))
    lines.append("")
    lines.extend(_market_table(result))
    lines.extend(_competition(result))
    lines.extend(_insights("## 4. 技术路线、商业模式与壁垒", result.technology_routes))
    lines.extend(_chain_table(result))
    if result.relationships:
        lines.append("### 上下游经营传导（条件推断，非已核实因果）")
        for edge in result.relationships:
            if edge.relation_type != "transmission":
                continue
            lines.extend(
                [
                    f"#### {edge.source_node} → {edge.target_node}",
                    f"冲击/变化：{edge.driver or '待补证'}",
                    f"目标经营指标：{edge.target_metric or '待补证'}",
                    f"机制：{edge.detail}",
                    f"成立条件：{'；'.join(edge.conditions) or '待补证'}",
                    f"传导时滞：{edge.time_lag or '未知，不假设即时兑现'}",
                    f"失效条件：{edge.invalidation or '待补证'}",
                    f"跟踪指标：{'；'.join(edge.tracking_metrics) or '待补证'}",
                    f"证据状态：{'前提片段已匹配，推导仍待复核' if edge.verification_status == 'quote_matched' else '前提待验证'}",
                ]
            )
            lines.extend(f"> {citation.quote} {_source('原文', citation.source_url)}" for citation in edge.citations)

    lines.extend(_insights("## 6. 关键趋势与催化剂", [*result.driver_insights, *result.trends]))
    lines.extend(_events(result))
    lines.extend(_companies(result))
    lines.extend(_insights("## 9. 风险提示", result.risk_insights))

    lines.append("## 证据覆盖与缺口")
    coverage_labels = {
        "market": "市场",
        "competition": "竞争",
        "technology": "技术",
        "chain": "产业链",
        "companies": "公司",
        "events": "事件",
    }
    coverage_status = {"complete": "完整", "partial": "部分", "missing": "缺失"}
    coverage = result.coverage.model_dump()
    lines.append("、".join(f"{coverage_labels[key]}：{coverage_status[value]}" for key, value in coverage.items()))
    if result.missing_evidence:
        lines.append("### 缺失证据")
        lines.extend(f"- {item}" for item in result.missing_evidence)
    lines.extend(_conflicts(result.conflicts))
    lines.append("")

    lines.append("## 10. 数据来源与口径说明")
    if result.sources:
        for source in result.sources:
            label = _source(source.title, source.url) or source.title
            metadata = " · ".join(value for value in (source.publisher, source.date) if value)
            evidence = _evidence(source.evidence_ids)
            suffix = "；".join(value for value in (metadata, evidence) if value)
            lines.append(f"- {label}{f'；{suffix}' if suffix else ''}")
    else:
        lines.append("暂无独立来源目录，请结合各项结论的来源与核验状态阅读。")
    if result.evidence_catalog:
        lines.extend(["", "### 资料索引（引用线索不代表事实核实）"])
        for entry in result.evidence_catalog:
            links = "、".join(
                _source(f"原文 {index + 1}", url) for index, url in enumerate(entry.source_urls) if safe_http_url(url)
            )
            lines.append(f"- {entry.evidence_id}：{entry.title or '研究资料'}；{links or '原文链接未提供'}")
    if result.relationships:
        lines.extend(["", "## 关系与定性传导"])
        for edge in result.relationships:
            lines.extend(
                [
                    f"- **{edge.source_node} → {edge.target_node}**：{edge.detail or edge.title}",
                    f"  - 成立条件：{'；'.join(edge.conditions) or '待补充'}；失效条件：{edge.invalidation or '待补充'}",
                    f"  - {_evidence(edge.evidence_ids)}；传导为条件假设，不作定量收益预测。",
                ]
            )
    if result.key_stocks:
        lines.extend(["", "## 公司业务相关度与验证"])
        relevance = {
            "unverified": "待验证",
            "concept": "概念布局",
            "business": "业务相关（待复核）",
            "earnings": "收入相关（待复核）",
        }
        for node in result.key_stocks:
            lines.extend(
                [
                    f"- **{_node_name(node)}**：{relevance[node.business_relevance]}",
                    f"  - 相关收入占比：{node.revenue_share or '未验证'}；统计期：{node.revenue_period or '待补充'}",
                    f"  - 受益路径：{node.benefit_path or '待补充'}",
                    f"  - 兑现条件：{'；'.join(node.realization_conditions) or '待补充'}",
                    f"  - 失效条件：{'；'.join(node.invalidation_conditions) or '待补充'}",
                    f"  - 跟踪指标：{'；'.join(node.tracking_metrics) or '待补充'}",
                ]
            )
    lines.extend(["", "## 关键指标原文核验"])
    for metric in result.market_metrics:
        status = "原文片段已匹配（仍需复核）" if metric.verification_status == "quote_matched" else "待验证"
        lines.append(
            f"- {metric.label}：{status}；统计期 {metric.period or '缺失'}；单位 {metric.unit or '缺失'}；地域 {metric.region or '缺失'}；口径 {metric.statistical_scope or '缺失'}"
        )
        for citation in metric.citations:
            lines.append(
                f"  - 原文：{citation.quote}；{_source('匹配原文', citation.source_url) if citation.source_url else _evidence([citation.evidence_id])}"
            )
    return "\n".join(lines).strip() + "\n"
