"""Deterministically render a validated daily review as Markdown."""

from app.modules.daily_review.models import DailyReviewResult, DailyReviewSection

_STATE_LABELS = {
    "attack": "进攻",
    "balanced": "均衡",
    "defensive": "防守",
    "unknown": "数据不足",
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
        lines.extend([f"> 请求日期 {result.requested_date}，实际复盘交易日 {result.effective_date or result.date}。", ""])
    lines.extend([
        "## 今日大盘复盘",
        f"**市场状态：{_STATE_LABELS[result.market_state]}**",
        result.market_summary or "核心数据不足，无法形成完整市场结论。",
        "",
    ])
    lines.extend(_section("### 1. 指数与量能", result.index_review))
    lines.extend(_section("### 2. 主线与板块轮动", result.hotspot_review))
    lines.extend(_section("### 3. 情绪与资金线索", result.dragon_tiger_review))
    lines.extend(_bullets("### 4. 机会方向", result.opportunities))
    lines.extend(_bullets("### 5. 风险提示", result.risk_alerts))

    lines.append("### 6. 明日交易计划")
    lines.append(f"- 建议仓位：{result.position_range or '数据不足，暂不设定仓位区间'}")
    lines.extend(f"- {item}" for item in result.strategy_notes)
    if result.invalid_conditions:
        lines.append("- 失效条件：" + "；".join(result.invalid_conditions))
    lines.append("")

    lines.append("## 数据覆盖与缺口")
    if result.data_gaps:
        lines.extend(f"- {item}" for item in result.data_gaps)
    else:
        lines.append("- 核心数据维度未发现明确缺口。")
    unavailable = [
        f"{name}：{status.error or '不可用'}"
        for name, status in result.data_snapshot.source_status.items()
        if status.status == "unavailable"
    ]
    lines.extend(f"- {item}" for item in unavailable)
    lines.extend(["", "以上内容仅供研究参考，不构成投资建议。"])
    return "\n".join(lines).strip() + "\n"
