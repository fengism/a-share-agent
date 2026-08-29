"""跨推送平台复用的内容块与领域内容构建器。"""

from __future__ import annotations

import re

from app.domain.content import ContentBlock
from app.modules.analysis.public import AnalysisResult, FactorAnalysis
from app.modules.daily_review.public import DailyReviewResult, DailyReviewSection

_SIGNAL_LABELS = {
    "strong_buy": "重点关注",
    "buy": "关注",
    "hold": "观察",
    "sell": "谨慎",
    "strong_sell": "回避",
}
_ACTION_LABELS = {
    "buy": "考虑买入",
    "watch": "继续观察",
    "avoid": "暂时回避",
    "hold": "继续持有",
    "add": "考虑增持",
    "reduce": "考虑减持",
    "exit": "考虑退出",
    "insufficient_evidence": "证据不足",
}
_MOAT_LABELS = {
    "brand_pricing": "品牌与定价权",
    "switching_cost": "转换成本",
    "network_effect": "网络效应",
    "scale_advantage": "规模优势",
    "technology_ip": "技术与知识产权",
    "other": "其他",
}
_LEVEL_LABELS = {
    "strong": "强",
    "moderate": "中",
    "weak": "弱",
    "strengthening": "增强",
    "stable": "稳定",
    "weakening": "减弱",
    "unclear": "待确认",
    "high": "高",
    "medium": "中",
    "low": "低",
    "unknown": "未知",
}


def _strip_markdown(text: str) -> str:
    """去除 markdown 粗体/斜体标记，保留纯文本。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _parse_markdown_blocks(text: str) -> list[ContentBlock]:
    """将 markdown 文本解析为 ContentBlock 列表，适配飞书文档呈现。"""
    blocks: list[ContentBlock] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            level = min(level, 3)
            blocks.append(ContentBlock(type="heading", level=level, text=_strip_markdown(heading_match.group(2))))
        elif stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ "):
            blocks.append(ContentBlock(type="bullet", text=_strip_markdown(stripped[2:])))
        elif re.match(r"^\d+[.)]\s+", stripped):
            content = re.sub(r"^\d+[.)]\s+", "", stripped)
            blocks.append(ContentBlock(type="bullet", text=_strip_markdown(content)))
        else:
            blocks.append(ContentBlock(type="paragraph", text=_strip_markdown(stripped)))
    return blocks


def build_content(data_type: str, data) -> list[ContentBlock]:
    """根据数据类型分发到对应的内容构建函数。

    Param:
        data_type: 数据类型标识，支持 "daily_review"、"analysis"、"chat"
        data: 对应类型的模型实例或原始文本
    Return:
        ContentBlock 列表，供飞书/Notion 适配器使用
    """
    if data_type == "daily_review":
        return _build_daily_review(data)
    if data_type == "analysis":
        return _build_analysis(data)
    if data_type == "chat":
        return _build_chat(data)
    if data_type == "industry_chain":
        return _build_industry_chain(data)
    raise ValueError(f"Unknown data_type: {data_type}")


def _build_chat(markdown_text: str) -> list[ContentBlock]:
    """将聊天消息的 markdown 文本解析为 ContentBlock 列表。

    Param:
        markdown_text: 含 markdown 标记的聊天内容
    Return:
        解析后的 ContentBlock 列表
    """
    return _parse_markdown_blocks(markdown_text)


def _build_daily_review(review: DailyReviewResult) -> list[ContentBlock]:
    """将每日复盘结果组装为 ContentBlock 列表。

    Param:
        review: 每日复盘结果模型
    Return:
        按章节顺序排列的 ContentBlock 列表
    """
    if review.schema_version >= 3 and review.llm_review.strip():
        return _parse_markdown_blocks(review.llm_review)

    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text="市场摘要"),
        ContentBlock(type="paragraph", text=review.market_summary),
        ContentBlock(type="paragraph", text=f"生成时间：{review.generated_at}"),
    ]
    if review.llm_review.strip():
        blocks.append(ContentBlock(type="heading", level=2, text="AI 复盘报告"))
        blocks.extend(_parse_markdown_blocks(review.llm_review))
    else:
        blocks.extend(_section_blocks(review.index_review))
        blocks.extend(_section_blocks(review.hotspot_review))
        blocks.extend(_section_blocks(review.dragon_tiger_review))
    blocks.append(ContentBlock(type="heading", level=2, text="机会"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.opportunities or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="风险"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.risk_alerts or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="策略"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.strategy_notes or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="原始数据摘要"))
    blocks.append(ContentBlock(type="paragraph", text=f"指数样本：{len(review.data_snapshot.indices)}；热点股：{len(review.data_snapshot.hot_stocks)}；龙虎榜：{len(review.data_snapshot.dragon_tiger)}"))
    return blocks


def _section_blocks(section: DailyReviewSection) -> list[ContentBlock]:
    """将每日复盘的单个章节渲染为 ContentBlock 列表。

    Param:
        section: 复盘章节模型，包含标题、摘要和要点列表
    Return:
        包含标题、摘要和要点的 ContentBlock 列表
    """
    blocks = [
        ContentBlock(type="heading", level=3, text=section.title),
        ContentBlock(type="paragraph", text=section.summary),
    ]
    blocks.extend(ContentBlock(type="bullet", text=item) for item in section.bullets)
    return blocks


def _build_analysis(result: AnalysisResult) -> list[ContentBlock]:
    """将个股分析结果组装为 ContentBlock 列表。

    Param:
        result: 个股分析结果模型
    Return:
        包含综合结论、各维度分析、关键因素和风险提示的 ContentBlock 列表
    """
    price_low, price_high = result.estimated_price_range
    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text="综合结论"),
        ContentBlock(type="paragraph", text=result.overall_summary),
        ContentBlock(
            type="paragraph",
            text=(
                f"当前价格：{result.current_price:.2f}；综合评分：{result.overall_rating}/10；"
                f"建议：{_SIGNAL_LABELS.get(result.signal, result.signal)}；置信度：{result.confidence:.0%}"
            ),
        ),
        ContentBlock(type="paragraph", text=f"目标价格区间：{price_low} - {price_high}"),
    ]
    blocks.extend(_factor_blocks("基本面", result.fundamental))
    blocks.extend(_factor_blocks("技术面", result.technical))
    blocks.extend(_factor_blocks("情绪面", result.sentiment))
    blocks.append(ContentBlock(type="heading", level=2, text="关键因素"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (result.key_factors or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="风险提示"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (result.risk_warnings or ["-"]))
    if result.research_framework:
        blocks.extend(_research_framework_blocks(result))
    return blocks


def _append_paragraph(blocks: list[ContentBlock], label: str, value: str) -> None:
    if value.strip():
        blocks.append(ContentBlock(type="paragraph", text=f"{label}：{value.strip()}"))


def _append_bullets(blocks: list[ContentBlock], label: str, items: list[str]) -> None:
    values = [item.strip() for item in items if item.strip()]
    if not values:
        return
    blocks.append(ContentBlock(type="paragraph", text=label))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in values)


def _format_range(value: tuple[float, float] | None) -> str:
    return "-" if value is None else f"{value[0]:.2f} - {value[1]:.2f}"


def _research_framework_blocks(result: AnalysisResult) -> list[ContentBlock]:
    research = result.research_framework
    if research is None:
        return []

    quality = research.information_quality
    blocks = [
        ContentBlock(type="divider"),
        ContentBlock(type="heading", level=2, text="深度研究结论"),
        ContentBlock(type="heading", level=3, text="证据质量"),
        ContentBlock(
            type="paragraph",
            text=(
                f"信息完备度：{quality.grade}；"
                f"证据可信度：{quality.evidence_confidence:.0%}" if quality.evidence_confidence is not None
                else f"信息完备度：{quality.grade}；证据可信度：待确认"
            ),
        ),
    ]
    if quality.investment_certainty is not None:
        blocks.append(ContentBlock(type="paragraph", text=f"投资确定性：{quality.investment_certainty:.0%}"))
    _append_paragraph(blocks, "覆盖摘要", quality.coverage_summary)
    _append_paragraph(blocks, "评级依据", quality.grade_rationale)
    _append_bullets(blocks, "解读限制", quality.limitations)

    business = research.business_model
    blocks.append(ContentBlock(type="heading", level=3, text="生意与盈利引擎"))
    _append_paragraph(blocks, "盈利引擎", business.economic_engine)
    _append_paragraph(blocks, "盈利质量", business.earnings_quality)
    _append_paragraph(blocks, "经营杠杆", business.operating_leverage)
    _append_bullets(blocks, "收入驱动", business.revenue_drivers)
    _append_bullets(blocks, "优势证据", business.strengths)
    _append_bullets(blocks, "待验证隐忧", business.concerns)

    blocks.append(ContentBlock(type="heading", level=3, text="护城河与反证"))
    _append_paragraph(blocks, "持续性判断", research.moat.overall_durability)
    for moat in research.moat.moats:
        label = _MOAT_LABELS.get(moat.moat_type, moat.moat_type)
        strength = _LEVEL_LABELS.get(moat.strength, moat.strength)
        direction = _LEVEL_LABELS.get(moat.direction, moat.direction)
        blocks.append(ContentBlock(type="paragraph", text=f"{label}（{strength}，{direction}）：{moat.durability or '待核验'}"))
        _append_bullets(blocks, "支持证据", moat.evidence)
        _append_bullets(blocks, "反证与威胁", [*moat.counterevidence, *moat.threats])
    _append_bullets(blocks, "关键威胁", research.moat.key_threats)

    blocks.append(ContentBlock(type="heading", level=3, text="管理层与行业位置"))
    _append_paragraph(blocks, "经营记录", research.management.track_record)
    _append_paragraph(blocks, "资本配置", research.management.capital_allocation)
    _append_paragraph(blocks, "股东利益一致性", research.management.shareholder_alignment)
    _append_paragraph(blocks, "关键人物风险", research.management.succession_or_key_person_risk)
    _append_paragraph(blocks, "长期行业背景", research.industry_position.secular_context)
    _append_paragraph(blocks, "价值链位置", research.industry_position.value_chain_position)
    _append_paragraph(blocks, "竞争位置", research.industry_position.competitive_position)
    _append_paragraph(blocks, "技术替代风险", research.industry_position.technology_or_obsolescence_risk)
    _append_bullets(blocks, "行业增长驱动", research.industry_position.growth_drivers)
    _append_bullets(blocks, "集中度风险", research.industry_position.concentration_risks)

    blocks.append(ContentBlock(type="heading", level=3, text="反向风险"))
    _append_paragraph(blocks, "最强熊市逻辑", research.inversion.bear_case)
    for risk in research.inversion.risks:
        probability = _LEVEL_LABELS.get(risk.probability, risk.probability)
        impact = _LEVEL_LABELS.get(risk.impact, risk.impact)
        blocks.append(ContentBlock(
            type="bullet",
            text=f"{risk.risk}（概率：{probability}；影响：{impact}）：{risk.failure_path or '失败路径待核验'}",
        ))
    _append_bullets(blocks, "认知偏差检查", research.inversion.bias_checks)

    valuation = research.valuation
    blocks.append(ContentBlock(type="heading", level=3, text="估值假设与情景"))
    _append_paragraph(blocks, "当前估值", valuation.current_valuation)
    _append_paragraph(blocks, "估值方法", valuation.method_summary)
    if valuation.scenarios:
        for label, scenario in (
            ("乐观", valuation.scenarios.bull),
            ("基准", valuation.scenarios.base),
            ("悲观", valuation.scenarios.bear),
        ):
            blocks.append(ContentBlock(
                type="bullet",
                text=f"{label}情景：{_format_range(scenario.fair_value_range)}；{scenario.valuation_view or '判断待确认'}",
            ))
    _append_paragraph(blocks, "安全边际", valuation.margin_of_safety)
    _append_bullets(blocks, "估值限制", valuation.limitations)

    actions = research.actions
    blocks.append(ContentBlock(type="heading", level=3, text="行动与持续跟踪"))
    blocks.append(ContentBlock(
        type="paragraph",
        text=(
            f"新投资者：{_ACTION_LABELS.get(actions.new_investor_action, actions.new_investor_action)}；"
            f"已持有者：{_ACTION_LABELS.get(actions.holder_action, actions.holder_action)}；"
            f"关注区间：{_format_range(actions.buy_or_add_range)}"
        ),
    ))
    _append_paragraph(blocks, "行动依据", actions.rationale)
    _append_bullets(blocks, "买入或加仓触发", actions.add_triggers)
    _append_bullets(blocks, "减持或卖出触发", actions.sell_triggers)
    _append_bullets(blocks, "核心逻辑失效条件", actions.thesis_breakers)
    _append_bullets(blocks, "持续跟踪指标", actions.monitoring_metrics)

    if research.data_gaps:
        blocks.append(ContentBlock(type="heading", level=3, text="数据缺口与下一步核验"))
        for gap in research.data_gaps:
            blocks.append(ContentBlock(
                type="bullet",
                text=f"{gap.topic}：{gap.missing_data or '缺失内容待确认'}；影响：{gap.decision_impact or '待评估'}；下一步：{gap.follow_up or '待补充'}",
            ))
    return blocks


def _build_industry_chain(result) -> list[ContentBlock]:
    """将产业链分析结果渲染为 ContentBlock 列表。

    Param:
        result: IndustryChainResult 对象或含相同字段的 dict
    Return:
        ContentBlock 列表
    """
    def _get(key, default=""):
        if isinstance(result, dict):
            return result.get(key, default)
        return getattr(result, key, default)

    llm_review = _get("llm_review", "").strip()
    if int(_get("schema_version", 1) or 1) >= 7 and llm_review:
        return _parse_markdown_blocks(llm_review)

    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text=f"{_get('name', '产业链')} 产业链分析"),
    ]
    summary = _get("summary", "").strip()
    if summary:
        blocks.append(ContentBlock(type="paragraph", text=summary))

    for stage_key, stage_title in (
        ("upstream", "上游"),
        ("midstream", "中游"),
        ("downstream", "下游"),
    ):
        items = _get(stage_key, []) or []
        if items:
            blocks.append(ContentBlock(type="heading", level=3, text=stage_title))
            for item in items:
                if isinstance(item, dict):
                    text = str(item.get("name") or item.get("code") or item)
                else:
                    text = str(item)
                blocks.append(ContentBlock(type="bullet", text=text))

    drivers = _get("drivers", []) or []
    if drivers:
        blocks.append(ContentBlock(type="heading", level=3, text="驱动因素"))
        blocks.extend(ContentBlock(type="bullet", text=str(d)) for d in drivers)

    risks = _get("risks", []) or []
    if risks:
        blocks.append(ContentBlock(type="heading", level=3, text="风险提示"))
        blocks.extend(ContentBlock(type="bullet", text=str(r)) for r in risks)

    key_stocks = _get("key_stocks", []) or []
    if key_stocks:
        blocks.append(ContentBlock(type="heading", level=3, text="重点关注"))
        for stock in key_stocks:
            if isinstance(stock, dict):
                text = str(stock.get("name") or stock.get("code") or stock)
            else:
                text = str(stock)
            blocks.append(ContentBlock(type="bullet", text=text))

    if llm_review:
        blocks.append(ContentBlock(type="heading", level=2, text="AI 复盘报告"))
        blocks.extend(_parse_markdown_blocks(llm_review))

    return blocks


def _factor_blocks(title: str, factor: FactorAnalysis) -> list[ContentBlock]:
    """将单维度因子分析渲染为 ContentBlock 列表。

    Param:
        title: 维度名称，如"基本面"
        factor: 因子分析模型
    Return:
        包含标题、摘要、优势和风险的 ContentBlock 列表
    """
    blocks = [
        ContentBlock(type="heading", level=3, text=f"{title}：{factor.score}/10"),
        ContentBlock(type="paragraph", text=factor.summary),
    ]
    if factor.strengths:
        blocks.append(ContentBlock(type="paragraph", text="优势"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in factor.strengths)
    if factor.risks:
        blocks.append(ContentBlock(type="paragraph", text="风险"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in factor.risks)
    return blocks
