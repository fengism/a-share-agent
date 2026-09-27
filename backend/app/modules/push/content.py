"""跨推送平台复用的内容块与领域内容构建器。"""

from __future__ import annotations

import re

from app.domain.content import ContentBlock
from app.modules.analysis.public import AnalysisResult, FactorAnalysis
from app.modules.daily_review.models import DailyReviewDataSnapshot
from app.modules.daily_review.public import DailyReviewResult, DailyReviewSection
from app.modules.daily_review.review_builder import group_limit_up_by_board

_SIGNAL_LABELS = {
    "strong_buy": "强烈买入",
    "buy": "买入 / 关注",
    "hold": "持有 / 观望",
    "sell": "减持 / 谨慎",
    "strong_sell": "强烈减持",
}

_ACTION_LABELS = {
    "buy": "买入",
    "watch": "重点关注",
    "avoid": "观望回避",
    "hold": "继续持有",
    "add": "逢低加仓",
    "reduce": "分批减仓",
    "exit": "坚决止损/离场",
    "insufficient_evidence": "待进一步核验",
}

_GRADE_LABELS = {
    "A": "A · 资料丰富 (High Quality)",
    "B": "B · 资料有限 (Moderate Quality)",
    "C": "C · 资料稀少 (Low Quality)",
    "unknown": "? · 尚未评级",
}

_MOAT_LABELS = {
    "brand_pricing": "品牌与定价权",
    "switching_cost": "转换成本",
    "network_effect": "网络效应",
    "scale_advantage": "规模优势",
    "technology_ip": "技术与知识产权",
    "other": "其他壁垒",
}

_LEVEL_LABELS = {
    "strong": "强",
    "moderate": "中",
    "weak": "弱",
    "strengthening": "增强 ↑",
    "stable": "稳定 →",
    "weakening": "减弱 ↓",
    "unclear": "待核验",
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
    "unknown": "待核验",
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
        data_type: 数据类型标识，支持 "daily_review"、"analysis"、"chat"、"industry_chain"
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
    """将聊天消息的 markdown 文本解析为 ContentBlock 列表。"""
    return _parse_markdown_blocks(markdown_text)


_STATE_LABELS = {
    "attack": "进攻",
    "balanced": "均衡",
    "defensive": "防守",
    "unknown": "数据不足",
}


def _format_pct(val: float | None) -> str:
    if val is None:
        return "-"
    return f"{'+' if val > 0 else ''}{val:.2f}%"


def _format_amt(val: float | None) -> str:
    if val is None:
        return "-"
    abs_val = abs(val)
    if abs_val >= 1e8:
        return f"{val / 1e8:.2f} 亿元"
    if abs_val >= 1e4:
        return f"{val / 1e4:.2f} 万元"
    return f"{val:.0f} 元"


def _build_daily_review_data_blocks(snapshot: DailyReviewDataSnapshot) -> list[ContentBlock]:
    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text="📊 核心市场数据看板"),
    ]

    # 1. 主要指数表现
    if snapshot.indices:
        blocks.append(ContentBlock(type="heading", level=3, text="主要指数表现"))
        for idx in snapshot.indices:
            name = idx.get("name") or idx.get("code") or "-"
            price = f"{idx.get('price'):.2f}" if idx.get("price") is not None else "-"
            chg = _format_pct(idx.get("change_pct"))
            amt = _format_amt(idx.get("amount"))
            blocks.append(ContentBlock(type="bullet", text=f"{name}：{price} ({chg}) ｜ 成交额 {amt}"))

    # 2. 量能与市场宽度
    has_vol = bool(snapshot.market_volume)
    has_stats = bool(snapshot.market_statistics)
    if has_vol or has_stats:
        blocks.append(ContentBlock(type="heading", level=3, text="量能与市场宽度"))
        if has_vol:
            total_amt = snapshot.market_volume.get("amount")
            prev_amt = snapshot.market_volume.get("amount_before_one_day")
            avg_20 = snapshot.market_volume.get("amount_average_20_day")
            avg_60 = snapshot.market_volume.get("amount_average_60_day")
            amt_str = _format_amt(total_amt)
            extra_parts = []
            if total_amt is not None and prev_amt is not None:
                diff = total_amt - prev_amt
                extra_parts.append(f"较前日 {'+' if diff > 0 else ''}{_format_amt(diff)}")
            if avg_20 is not None:
                extra_parts.append(f"20日均值 {_format_amt(avg_20)}")
            if avg_60 is not None:
                extra_parts.append(f"60日均值 {_format_amt(avg_60)}")
            extra_str = f"（{'，'.join(extra_parts)}）" if extra_parts else ""
            blocks.append(ContentBlock(type="bullet", text=f"两市总成交额：{amt_str}{extra_str}".strip()))

        if has_stats:
            up = snapshot.market_statistics.get("up_count", 0)
            down = snapshot.market_statistics.get("down_count", 0)
            flat = snapshot.market_statistics.get("flat_count", 0)
            limit_up = snapshot.market_statistics.get("limit_up_count", 0)
            limit_down = snapshot.market_statistics.get("limit_down_count", 0)
            blocks.append(ContentBlock(type="bullet", text=f"涨跌分布：上涨 {up} 家 ｜ 平盘 {flat} 家 ｜ 下跌 {down} 家"))
            blocks.append(ContentBlock(type="bullet", text=f"涨跌停数：涨停 {limit_up} 家 ｜ 跌停 {limit_down} 家"))

    # 2.5 连板天梯与短线情绪
    if snapshot.limit_up_ladder and snapshot.limit_up_ladder.get("stocks"):
        ladder_stocks = snapshot.limit_up_ladder.get("stocks") or []
        by_board = group_limit_up_by_board(ladder_stocks)
        max_board = max(by_board) if by_board else 0
        top_stocks = by_board.get(max_board, [])
        top_names = "、".join(s.get("name") for s in top_stocks[:3] if s.get("name"))
        ladder_summary = " ｜ ".join(
            f"{b}板 {len(stks)}家"
            for b, stks in sorted(by_board.items(), reverse=True)
            if b > 1
        )
        first_count = len(by_board.get(1, []))
        if first_count:
            ladder_summary += f" ｜ 首板 {first_count}家"
        blocks.append(ContentBlock(type="heading", level=3, text="短线连板天梯"))
        blocks.append(ContentBlock(type="bullet", text=f"最高空间板：{max_board}板（{top_names}）"))
        if ladder_summary:
            blocks.append(ContentBlock(type="bullet", text=f"连板梯队分布：{ladder_summary}"))

    # 2.6 北向资金
    if snapshot.northbound_funds and snapshot.northbound_funds.get("north_money") is not None:
        north = snapshot.northbound_funds.get("north_money")
        sign = "+" if north > 0 else ""
        blocks.append(ContentBlock(type="bullet", text=f"北向资金净买入：{sign}{north:.2f} 亿元"))

    # 3. 行业板块涨跌榜 (TOP 5)
    if snapshot.top_sectors or snapshot.bottom_sectors:
        blocks.append(ContentBlock(type="heading", level=3, text="行业板块涨跌榜 (TOP 5)"))
        if snapshot.top_sectors:
            top_items = []
            for s in snapshot.top_sectors[:5]:
                sec_name = s.get("name") or "-"
                sec_chg = _format_pct(s.get("change_pct"))
                lead = s.get("leading_stock") or ""
                lead_chg = f" ({lead} {_format_pct(s.get('leading_change_pct'))})" if lead else ""
                top_items.append(f"{sec_name} {sec_chg}{lead_chg}")
            blocks.append(ContentBlock(type="bullet", text="领涨行业：" + " ｜ ".join(top_items)))
        if snapshot.bottom_sectors:
            bot_items = []
            for s in snapshot.bottom_sectors[:5]:
                sec_name = s.get("name") or "-"
                sec_chg = _format_pct(s.get("change_pct"))
                lead = s.get("leading_stock") or ""
                lead_chg = f" ({lead} {_format_pct(s.get('leading_change_pct'))})" if lead else ""
                bot_items.append(f"{sec_name} {sec_chg}{lead_chg}")
            blocks.append(ContentBlock(type="bullet", text="领跌行业：" + " ｜ ".join(bot_items)))

    # 4. 龙虎榜活跃资金动向 (TOP 5)
    if snapshot.dragon_tiger:
        blocks.append(ContentBlock(type="heading", level=3, text="龙虎榜机构与活跃资金 (TOP 5)"))
        for item in snapshot.dragon_tiger[:5]:
            stk_name = item.get("name") or item.get("code") or "-"
            stk_code = item.get("code") or ""
            net_amt = _format_amt(item.get("net_amount"))
            chg = _format_pct(item.get("change_pct"))
            blocks.append(ContentBlock(type="bullet", text=f"{stk_name} ({stk_code})：净买入 {net_amt} ｜ 涨跌幅 {chg}"))

    # 5. 热点题材概念
    if snapshot.hot_concepts:
        concepts = [str(c.get("name", "")).strip() for c in snapshot.hot_concepts[:8] if c.get("name")]
        if concepts:
            blocks.append(ContentBlock(type="bullet", text="热点概念：" + "、".join(concepts)))

    return blocks


def _build_daily_review(review: DailyReviewResult) -> list[ContentBlock]:
    """将每日复盘结果组装为 ContentBlock 列表。"""
    date_str = review.effective_date or review.date
    state_label = _STATE_LABELS.get(review.market_state, "未知")

    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=1, text=f"📅 {date_str} A 股每日市场复盘"),
        ContentBlock(type="paragraph", text=f"市场状态：{state_label} ｜ 建议仓位：{review.position_range or '灵活配置'}"),
    ]
    if review.market_summary.strip():
        blocks.append(ContentBlock(type="paragraph", text=review.market_summary.strip()))

    # 插入核心市场数据看板（指数、市场宽度、行业排行、龙虎榜等）
    if review.data_snapshot:
        data_blocks = _build_daily_review_data_blocks(review.data_snapshot)
        if len(data_blocks) > 1:
            blocks.extend(data_blocks)
            blocks.append(ContentBlock(type="divider"))

    # 插入 AI 复盘详细报告
    blocks.append(ContentBlock(type="heading", level=2, text="📝 AI 深度复盘研报"))
    if review.llm_review.strip():
        parsed = _parse_markdown_blocks(review.llm_review)
        for b in parsed:
            if b.type == "heading" and (
                (b.level == 1 and "每日市场复盘" in b.text)
                or (b.level == 2 and "今日大盘复盘" in b.text)
            ):
                continue
            blocks.append(b)
    else:
        blocks.extend(_section_blocks(review.index_review))
        blocks.extend(_section_blocks(review.hotspot_review))
        blocks.extend(_section_blocks(review.dragon_tiger_review))
        blocks.append(ContentBlock(type="heading", level=3, text="机会方向"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.opportunities or ["-"]))
        blocks.append(ContentBlock(type="heading", level=3, text="风险提示"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.risk_alerts or ["-"]))
        blocks.append(ContentBlock(type="heading", level=3, text="策略指引"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.strategy_notes or ["-"]))

    return blocks


def _section_blocks(section: DailyReviewSection) -> list[ContentBlock]:
    """将每日复盘的单个章节渲染为 ContentBlock 列表。"""
    blocks = [
        ContentBlock(type="heading", level=3, text=section.title),
        ContentBlock(type="paragraph", text=section.summary),
    ]
    blocks.extend(ContentBlock(type="bullet", text=item) for item in section.bullets)
    return blocks


def _append_paragraph(blocks: list[ContentBlock], label: str, value: str | None) -> None:
    if value and str(value).strip():
        blocks.append(ContentBlock(type="paragraph", text=f"{label}：{str(value).strip()}"))


def _append_bullets(blocks: list[ContentBlock], label: str, items: list[str]) -> None:
    values = [str(item).strip() for item in items if item and str(item).strip()]
    if not values:
        return
    blocks.append(ContentBlock(type="paragraph", text=label))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in values)


def _format_range(value: tuple[float, float] | list[float] | None) -> str:
    if not value or len(value) != 2:
        return "证据不足 · 待核验"
    if value[0] <= 0 and value[1] <= 0:
        return "证据不足 · 待核验"
    return f"¥{value[0]:.2f} - ¥{value[1]:.2f}"


def _build_analysis(result: AnalysisResult) -> list[ContentBlock]:
    """将个股深度分析结果组装为 ContentBlock 列表，全面 1:1 对齐 PDF 研报的 8 大标准章节与数据。"""
    code = getattr(result, "stock_code", None) or getattr(result, "code", "")
    name = getattr(result, "stock_name", None) or getattr(result, "name", "") or code
    date = getattr(result, "analysis_date", "") or "最新"
    signal_label = _SIGNAL_LABELS.get(result.signal, str(result.signal))
    confidence_pct = f"{int(result.confidence * 100)}%"
    current_price = f"¥{result.current_price:.2f}" if result.current_price is not None and result.current_price > 0 else "--"
    
    rf = getattr(result, "research_framework", None)
    est_range = getattr(result, "estimated_price_range", None)
    fair_range = getattr(result, "fair_value_range", None)
    base_range = rf.valuation.scenarios.base.fair_value_range if rf and rf.valuation and rf.valuation.scenarios and rf.valuation.scenarios.base else None
    
    if est_range and est_range[0] > 0 and est_range[1] > 0:
        target_range_str = f"¥{est_range[0]:.2f} - ¥{est_range[1]:.2f}"
    elif fair_range and fair_range[0] > 0 and fair_range[1] > 0:
        target_range_str = f"¥{fair_range[0]:.2f} - ¥{fair_range[1]:.2f}"
    elif base_range and base_range[0] > 0 and base_range[1] > 0:
        target_range_str = f"¥{base_range[0]:.2f} - ¥{base_range[1]:.2f}"
    else:
        target_range_str = "证据不足 · 待核验"

    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=1, text=f"{name} ({code}) · 深度价值投资研报"),
        ContentBlock(
            type="paragraph",
            text=(
                f"【核心研判】{signal_label} ｜ 目标区间：{target_range_str} ｜ "
                f"最新参考价：{current_price} ｜ 综合评分：{result.overall_rating}/10 ｜ "
                f"系统置信度：{confidence_pct} ｜ 研究基准日：{date}"
            ),
        ),
        ContentBlock(type="heading", level=2, text="💡 综合投资结论与核心投资逻辑"),
        ContentBlock(type="paragraph", text=result.overall_summary or "根据深度研究框架，当前公司具备明确的竞争优势与估值支撑。"),
    ]

    if rf:
        # 01 · 信息质量与证据链
        quality = rf.information_quality
        q_grade = _GRADE_LABELS.get(quality.grade, quality.grade)
        blocks.extend([
            ContentBlock(type="heading", level=2, text="01 · 信息质量与证据链 (Information Quality)"),
            ContentBlock(type="paragraph", text=f"资料完备度评级：{q_grade}"),
        ])
        if quality.coverage_summary:
            _append_paragraph(blocks, "覆盖摘要", quality.coverage_summary)
        if quality.grade_rationale:
            _append_paragraph(blocks, "评级依据", quality.grade_rationale)
        cert_text = f"{int(quality.investment_certainty * 100)}%" if quality.investment_certainty is not None else confidence_pct
        conf_text = f"{int(quality.evidence_confidence * 100)}%" if quality.evidence_confidence is not None else confidence_pct
        blocks.append(ContentBlock(type="paragraph", text=f"证据链置信度：{conf_text} ｜ 投资确定性：{cert_text}"))
        _append_bullets(blocks, "核心局限与已知盲区", quality.limitations)

        # 02 · 商业模式与盈利质量
        business = rf.business_model
        blocks.append(ContentBlock(type="heading", level=2, text="02 · 商业模式与盈利质量 (Business Model)"))
        _append_paragraph(blocks, "核心经济引擎 (Economic Engine)", business.economic_engine)
        _append_paragraph(blocks, "盈利质量", business.earnings_quality)
        _append_paragraph(blocks, "经营杠杆效应", business.operating_leverage)
        _append_bullets(blocks, "核心收入驱动力", business.revenue_drivers)
        _append_bullets(blocks, "竞争优势支撑证据", business.strengths)
        _append_bullets(blocks, "待验证隐忧与风险", business.concerns)
        if business.segment_quality:
            blocks.append(ContentBlock(type="paragraph", text="主营分部质量明细评估："))
            for seg in business.segment_quality:
                role = f" ({seg.role})" if seg.role else ""
                conf_str = f" ｜ {int(seg.evidence_confidence * 100)}% 证据" if seg.evidence_confidence is not None else ""
                blocks.append(ContentBlock(
                    type="bullet",
                    text=f"{seg.segment}{role}{conf_str}：增长质量[{seg.growth_quality or '--'}] ｜ 盈利质量[{seg.profitability_quality or '--'}] ｜ 现金重现[{seg.recurrence or '--'}]",
                ))

        # 03 · 护城河与竞争壁垒
        moat = rf.moat
        blocks.append(ContentBlock(type="heading", level=2, text="03 · 护城河与竞争壁垒 (Economic Moat)"))
        _append_paragraph(blocks, "整体壁垒持续性", moat.overall_durability)
        for m in moat.moats:
            m_name = _MOAT_LABELS.get(m.moat_type, m.moat_type)
            m_strength = _LEVEL_LABELS.get(m.strength, m.strength)
            m_dir = _LEVEL_LABELS.get(m.direction, m.direction)
            blocks.append(ContentBlock(
                type="paragraph",
                text=f"【{m_name}】强度：{m_strength} ｜ 趋势：{m_dir} ｜ 持续期限：{m.durability or '长期稳固'}",
            ))
            _append_bullets(blocks, "  支撑证据", m.evidence)
            if m.counterevidence or m.threats:
                _append_bullets(blocks, "  反证与潜在威胁", [*m.counterevidence, *m.threats])
        _append_bullets(blocks, "⚠️ 关键外部威胁 (Key Threats)", moat.key_threats)

        # 04 · 管理层能力与资本配置
        mgmt = rf.management
        blocks.append(ContentBlock(type="heading", level=2, text="04 · 管理层能力与资本配置 (Management & Stewardship)"))
        _append_paragraph(blocks, "历史经营记录 (Track Record)", mgmt.track_record)
        _append_paragraph(blocks, "资本配置效率 (Capital Allocation)", mgmt.capital_allocation)
        _append_paragraph(blocks, "股东利益一致性 (Alignment)", mgmt.shareholder_alignment)
        _append_paragraph(blocks, "传承与关键人物风险 (Key Person Risk)", mgmt.succession_or_key_person_risk)
        _append_bullets(blocks, "管理层优势", mgmt.strengths)
        _append_bullets(blocks, "治理与管理隐忧", mgmt.concerns)

        # 05 · 行业格局与产业链地位
        ind = rf.industry_position
        blocks.append(ContentBlock(type="heading", level=2, text="05 · 行业格局与产业链地位 (Industry Landscape)"))
        _append_paragraph(blocks, "行业长期趋势与格局", ind.secular_context)
        _append_paragraph(blocks, "产业链价值位置", ind.value_chain_position)
        _append_paragraph(blocks, "竞争地位", ind.competitive_position)
        _append_paragraph(blocks, "技术替代风险", ind.technology_or_obsolescence_risk)
        _append_bullets(blocks, "行业核心增长驱动力", ind.growth_drivers)
        _append_bullets(blocks, "行业集中度与上下游风险", ind.concentration_risks)

        # 06 · 逆向推演与主要风险清单
        inversion = rf.inversion
        blocks.append(ContentBlock(type="heading", level=2, text="06 · 逆向推演与主要风险清单 (Inversion & Risks)"))
        _append_paragraph(blocks, "最强看空逻辑推演 (Bear Case)", inversion.bear_case)
        if inversion.risks:
            for r in inversion.risks:
                r_prob = _LEVEL_LABELS.get(r.probability, r.probability)
                r_imp = _LEVEL_LABELS.get(r.impact, r.impact)
                horizon = f" ｜ 观察窗口: {r.time_horizon}" if getattr(r, "time_horizon", None) else ""
                blocks.append(ContentBlock(
                    type="bullet",
                    text=f"⚠️ {r.risk}（发生概率：{r_prob} ｜ 潜在影响：{r_imp}{horizon}）",
                ))
                if r.failure_path:
                    blocks.append(ContentBlock(type="paragraph", text=f"    - 逻辑失效路径：{r.failure_path}"))
                if r.leading_indicators:
                    blocks.append(ContentBlock(type="paragraph", text=f"    - 先行预警指标：{', '.join(r.leading_indicators)}"))
                if r.mitigants:
                    blocks.append(ContentBlock(type="paragraph", text=f"    - 对冲缓解措施：{', '.join(r.mitigants)}"))
        _append_bullets(blocks, "认知偏差与假设自查 (Bias Checks)", inversion.bias_checks)

        # 07 · 估值假设与三情景推演
        valuation = rf.valuation
        blocks.append(ContentBlock(type="heading", level=2, text="07 · 估值假设与三情景推演 (Valuation Scenarios)"))
        _append_paragraph(blocks, "当前估值状态", valuation.current_valuation)
        _append_paragraph(blocks, "估值方法与模型", valuation.method_summary)
        _append_paragraph(blocks, "安全边际判断", valuation.margin_of_safety)
        if valuation.scenarios:
            for sc_name, sc_obj in (
                ("乐观情景 (Bull)", valuation.scenarios.bull),
                ("基准情景 (Base)", valuation.scenarios.base),
                ("悲观情景 (Bear)", valuation.scenarios.bear),
            ):
                sc_range = _format_range(sc_obj.fair_value_range)
                blocks.append(ContentBlock(
                    type="paragraph",
                    text=f"【{sc_name}】公允区间：{sc_range} ｜ 核心判断：{sc_obj.valuation_view or '业务稳健推进'}",
                ))
                _append_bullets(blocks, "  关键假设", sc_obj.assumptions)
                if sc_obj.invalidating_conditions:
                    _append_bullets(blocks, "  情景失效条件", sc_obj.invalidating_conditions)
        _append_bullets(blocks, "共同估值假设", valuation.assumptions)
        _append_bullets(blocks, "估值模型局限", valuation.limitations)

        # 08 · 投资行动建议与监控体系
        actions = rf.actions
        blocks.append(ContentBlock(type="heading", level=2, text="08 · 投资行动建议与监控体系 (Action & Monitoring)"))
        new_inv_act = _ACTION_LABELS.get(actions.new_investor_action, actions.new_investor_action)
        holder_act = _ACTION_LABELS.get(actions.holder_action, actions.holder_action)
        buy_range = _format_range(actions.buy_or_add_range) if actions.buy_or_add_range else target_range_str
        blocks.append(ContentBlock(
            type="paragraph",
            text=f"新投资者行动：{new_inv_act} ｜ 持仓管理操作：{holder_act} ｜ 建议买入/增持区间：{buy_range}",
        ))
        _append_paragraph(blocks, "决策行动逻辑依据", actions.rationale)
        _append_bullets(blocks, "新投资者买入/关注触发条件", actions.add_triggers)
        _append_bullets(blocks, "已持有者减持/退出触发条件", actions.sell_triggers)
        _append_bullets(blocks, "🚨 核心逻辑失效条件 (Thesis Breakers)", actions.thesis_breakers)
        _append_bullets(blocks, "📊 持续跟踪指标 (Monitoring Metrics)", actions.monitoring_metrics)

        # 09 · 数据缺口与待核验清单
        if rf.data_gaps:
            blocks.append(ContentBlock(type="heading", level=2, text="09 · 数据缺口与待核验清单 (Data Gaps)"))
            for gap in rf.data_gaps:
                blocks.append(ContentBlock(
                    type="bullet",
                    text=f"{gap.topic}：{gap.missing_data or '缺失内容待补全'}（影响：{gap.decision_impact or '待评估'} ｜ 下一步：{gap.follow_up or '待核验'}）",
                ))
    else:
        # 兼容传统三因子分析
        blocks.extend(_factor_blocks("基本面", result.fundamental))
        blocks.extend(_factor_blocks("技术面", result.technical))
        blocks.extend(_factor_blocks("情绪面", result.sentiment))
        blocks.append(ContentBlock(type="heading", level=2, text="关键因素"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in (result.key_factors or ["-"]))
        blocks.append(ContentBlock(type="heading", level=2, text="风险提示"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in (result.risk_warnings or ["-"]))

    # 研报合规免责声明
    blocks.append(ContentBlock(type="divider"))
    blocks.append(ContentBlock(
        type="paragraph",
        text="【研究声明与免责提示】本报告由 A股智能投研体系基于公开披露数据与算法模型自动生成，旨在辅助客观框架化研究，不构成任何形式的直接投资建议或保本承诺。证券市场有风险，投资决策需建立在独立判断之上。",
    ))

    return blocks


def _build_industry_chain(result) -> list[ContentBlock]:
    """将产业链分析结果渲染为 ContentBlock 列表。"""
    from app.modules.industry_chain.presentation import presentation_payload
    result = presentation_payload(result)
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
    """将单维度因子分析渲染为 ContentBlock 列表。"""
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
