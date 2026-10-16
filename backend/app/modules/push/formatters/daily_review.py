"""每日复盘通知格式化器。"""

from __future__ import annotations

from typing import Any

from app.modules.daily_review.models import DailyReviewResult
from app.modules.push.domain.message import NotificationMessage, NotificationSeverity
from app.modules.push.formatters.base import NotificationFormatter


def format_daily_review_feishu_card(review: DailyReviewResult) -> dict[str, Any]:
    """格式化每日收盘复盘飞书交互式卡片。"""
    indices_summary = []
    for item in review.data_snapshot.indices[:3]:
        chg = item.get("change_pct")
        chg_str = f"{chg:+.2f}%" if chg is not None else "-"
        indices_summary.append(f"**{item.get('name', '')}**: {chg_str}")
    indices_line = "  |  ".join(indices_summary) if indices_summary else "指数平稳"

    stage = review.sentiment_cycle.stage if review.sentiment_cycle else "中性"
    state_map = {"attack": "进攻", "defensive": "防守", "balanced": "均衡", "unknown": "观望"}
    market_state = state_map.get(review.market_state, review.market_state)

    sectors = [s.get("name") for s in review.data_snapshot.top_sectors[:4] if s.get("name")]
    sectors_line = "、".join(sectors) if sectors else "暂无"

    watchlist_items = []
    for w in review.next_day_watchlist[:3]:
        watchlist_items.append(f"• **{w.name}** ({w.code}): {w.role} - {w.trigger or w.reason}")
    watchlist_text = "\n".join(watchlist_items) if watchlist_items else "无重点观察标的"

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"📊 **指数概览**：\n{indices_line}\n\n"
                           f"🎯 **市场定调**：阶段 **{stage}**  |  策略建议 **{market_state}**  |  仓位建议 **{review.position_range or '适中'}**\n\n"
                           f"🔥 **领涨板块**：{sectors_line}\n\n"
                           f"📝 **市场总结**：\n{review.market_summary[:300]}...",
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"🔍 **次日核心锚点**：\n{watchlist_text}",
            },
        },
    ]

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📈 A股每日收盘复盘 · {review.date}"},
            "template": "blue" if review.market_state != "defensive" else "orange",
        },
        "elements": elements,
    }


def format_daily_review_wecom_markdown(review: DailyReviewResult) -> str:
    """格式化每日收盘复盘企业微信与通用 Markdown。"""
    indices_summary = []
    for item in review.data_snapshot.indices[:3]:
        chg = item.get("change_pct")
        chg_str = f"{chg:+.2f}%" if chg is not None else "-"
        indices_summary.append(f"{item.get('name', '')} {chg_str}")
    indices_line = " | ".join(indices_summary) if indices_summary else "指数平稳"

    stage = review.sentiment_cycle.stage if review.sentiment_cycle else "中性"
    state_map = {"attack": "进攻", "defensive": "防守", "balanced": "均衡", "unknown": "观望"}
    market_state = state_map.get(review.market_state, review.market_state)

    sectors = [s.get("name") for s in review.data_snapshot.top_sectors[:4] if s.get("name")]
    sectors_line = "、".join(sectors) if sectors else "暂无"

    watchlist_items = []
    for w in review.next_day_watchlist[:3]:
        watchlist_items.append(f"- **{w.name}** ({w.code}) [{w.role}]: {w.trigger or w.reason}")
    watchlist_text = "\n".join(watchlist_items) if watchlist_items else "- 无重点观察标的"

    return f"""### 📈 A股每日收盘复盘 · {review.date}
> 指数表现：<font color="info">{indices_line}</font>
> 情绪周期：**{stage}** | 建议仓位：**{review.position_range or '适中'}** ({market_state})
> 领涨题材：{sectors_line}

**市场综述**
{review.market_summary[:260]}...

**次日关注锚点**
{watchlist_text}
"""


class DailyReviewFormatter(NotificationFormatter[DailyReviewResult]):
    """将每日复盘结果转化为标准 NotificationMessage。"""

    def format(self, payload: DailyReviewResult) -> NotificationMessage:
        title = f"A股每日收盘复盘 · {payload.date}"
        markdown = format_daily_review_wecom_markdown(payload)
        card = format_daily_review_feishu_card(payload)
        severity = NotificationSeverity.WARNING if payload.market_state == "defensive" else NotificationSeverity.INFO

        return NotificationMessage(
            title=title,
            summary=payload.market_summary[:100],
            markdown_body=markdown,
            severity=severity,
            category="daily_review",
            card_data=card,
            metadata={"date": payload.date, "market_state": payload.market_state},
        )


daily_review_formatter = DailyReviewFormatter()
