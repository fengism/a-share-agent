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


def _pct(value: float | None, *, signed: bool = True) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


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
    if result.sentiment_cycle is not None:
        cycle = result.sentiment_cycle
        lines.append(f"#### 情绪周期定位：{cycle.stage}")
        lines.append(f"- 梯队健康度：{cycle.ladder_health or '待补充'}")
        lines.extend(f"- 依据：{item}" for item in cycle.evidence)
        lines.append("")
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

    if result.scenario_plans:
        lines.append("#### 明日三情景预案")
        for scenario in result.scenario_plans:
            lines.append(
                f"- **{scenario.name}**：触发 {scenario.trigger or '待补充'}；应对 {scenario.playbook or '待补充'}"
            )
            if scenario.watch_levels:
                lines.append(f"  - 观察信号：{'；'.join(scenario.watch_levels)}")
        lines.append("")

    if result.next_day_watchlist:
        lines.append("#### 次日观察锚点")
        for watch in result.next_day_watchlist:
            lines.append(
                f"- **{watch.name}**（{watch.role}）：{watch.reason or '待补充'}；触发 {watch.trigger or '待补充'}"
            )
        lines.append("")

    if result.key_levels:
        lines.extend(_bullets("#### 关键点位与量能阈值", result.key_levels))

    check = result.previous_review_check
    if check is not None:
        lines.append(f"## 上一交易日复盘自检（{check.review_date} → {check.verified_date}）")
        if check.previous_stage:
            lines.append(f"- 上一交易日周期定位：{check.previous_stage}")
        if check.previous_limit_up_count is not None and check.limit_up_count is not None:
            lines.append(f"- 涨停家数：{check.previous_limit_up_count} → {check.limit_up_count}")
        for index in check.indices:
            if index.change_pct is None and index.previous_change_pct is None:
                continue
            lines.append(f"- {index.name}：{_pct(index.previous_change_pct)} → {_pct(index.change_pct)}")
        for item in check.watchlist:
            if item.missing:
                lines.append(f"- {item.name}：次日行情缺失")
                continue
            extra = "，次日涨停" if item.limit_up else ""
            lines.append(f"- {item.name}：次日 {_pct(item.change_pct)}{extra}（{'命中' if item.hit else '落空'}）")
        if check.checked_count:
            lines.append(
                f"- 观察标的命中率：{check.hit_count}/{check.checked_count}"
                f"（{_pct(check.hit_rate, signed=False)}）"
            )
        if check.note:
            lines.append(f"- 说明：{check.note}")
        lines.append("")

    trend = result.cycle_trend
    if trend is not None and (trend.points or trend.note):
        lines.append("## 情绪周期历史趋势")
        if trend.note:
            lines.append(f"- 说明：{trend.note}")
        for point in trend.points[-10:]:
            parts = [point.date, point.stage or "未定位"]
            if point.limit_up_count is not None:
                parts.append(f"涨停 {point.limit_up_count} 家")
            if point.break_rate is not None:
                parts.append(f"炸板率 {point.break_rate:.1%}")
            if point.index_change_pct is not None:
                parts.append(f"指数 {_pct(point.index_change_pct)}")
            if point.next_index_change_pct is not None:
                parts.append(f"次日指数 {_pct(point.next_index_change_pct)}")
            if point.stage_transition:
                parts.append(point.stage_transition)
            lines.append("- " + "；".join(parts))
        for stat in trend.stage_stats:
            lines.append(
                f"- 阶段统计：{stat.stage} 出现 {stat.occurrences} 次，"
                f"次日上涨比例 {_pct(stat.next_day_up_ratio, signed=False)}，"
                f"平均次日指数 {_pct(stat.avg_next_day_index_change_pct)}"
            )
        lines.append("")

    lines.append("## 数据覆盖与核验状态")
    lines.extend(f"- ⚠️ {item}" for item in result.warnings)
    lines.extend(f"- 说明：{item}" for item in result.notes)
    if result.data_gaps:
        lines.extend(f"- {item}" for item in result.data_gaps)
    elif not result.warnings and not result.notes:
        lines.append("- 核心数据维度未发现明确缺口。")
    lines.extend(["", "以上内容仅供研究参考，不构成投资建议。"])
    return "\n".join(lines).strip() + "\n"
