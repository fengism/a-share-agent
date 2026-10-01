"""Deterministically render a validated daily review as Markdown."""

from app.modules.daily_review.models import DailyReviewResult, DailyReviewSection

_STATE_LABELS = {
    "attack": "进攻型（多头主导/放量突破）",
    "balanced": "均衡型（震荡整固/存量博弈）",
    "defensive": "防守型（空头占优/退潮防守）",
    "unknown": "数据不足（审慎评估）",
}


def _section(title: str, section: DailyReviewSection) -> list[str]:
    lines = [title]
    if section.summary:
        lines.append(section.summary)
    lines.extend(f"- {item}" for item in section.bullets)
    if not section.summary and not section.bullets:
        lines.append("数据不足。")
    lines.append("")
    return lines


def _bullets(title: str, values: list[str], empty: str = "暂无可靠结论。") -> list[str]:
    lines = [title]
    lines.extend(f"- {item}" for item in values) if values else lines.append(empty)
    lines.append("")
    return lines


def render_daily_review_markdown(result: DailyReviewResult) -> str:
    lines = [f"# {result.date} 每日市场复盘", ""]
    if result.requested_date and result.requested_date != result.effective_date:
        lines.extend([f"> 提示：请求日期 {result.requested_date} 为非交易日或盘中时间，实际复盘基准交易日为 **{result.effective_date or result.date}**。", ""])
    lines.extend([
        "## 今日大盘复盘",
        f"**市场状态：{_STATE_LABELS.get(result.market_state, '未知')}** ｜ **建议仓位：{result.position_range or '灵活控制'}**",
        result.market_summary or "核心数据不足，无法形成完整市场结论。",
        "",
    ])
    lines.extend(_section("### 1. 指数与量价格局", result.index_review))
    lines.extend(_section("### 2. 板块轮动与题材生命周期", result.hotspot_review))
    lines.extend(_section("### 3. 情绪周期与资金微观动向", result.dragon_tiger_review))
    lines.extend(_section("### 4. 新闻政策与影响传导", result.news_policy_review))
    if result.event_impacts:
        lines.append("#### 重点事件传导矩阵")
        for impact in result.event_impacts:
            sectors = "、".join(impact.affected_sectors) or "市场整体"
            lines.extend([
                f"- **{impact.event_title}**（{impact.direction} / {impact.horizon} / {impact.timing}）",
                f"  - 影响方向：{sectors}",
                f"  - 传导链：{impact.transmission_chain or '待盘面验证'}",
                f"  - 证据：{impact.evidence or '来源不足'}",
                f"  - 盘面验证：{impact.market_confirmation or '尚未核验'}",
                f"  - 确认信号：{'；'.join(impact.confirmation_signals) or '待观察'}",
                f"  - 失效条件：{'；'.join(impact.invalidation_conditions) or '待观察'}",
            ])
        lines.append("")
    lines.extend(_bullets("### 5. 机会方向与低吸逻辑", result.opportunities))
    lines.extend(_bullets("### 6. 风险预警与雷区提示", result.risk_alerts))

    lines.append("### 7. 明日交易计划与情景推演")
    lines.append(f"- 建议仓位：{result.position_range or '数据不足，暂不设定仓位区间'}")
    lines.extend(f"- {item}" for item in result.strategy_notes)
    if result.invalid_conditions:
        lines.append("- 策略失效条件：" + "；".join(result.invalid_conditions))
    lines.append("")

    lines.append("## 数据覆盖与核验状态")
    if result.data_gaps:
        lines.extend(f"- {item}" for item in result.data_gaps)
    else:
        lines.append("- 核心数据维度未发现明确缺口。")
    lines.extend(["", "以上内容仅供研究参考，不构成投资建议。"])
    return "\n".join(lines).strip() + "\n"
