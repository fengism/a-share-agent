"""题材挖掘与潜力个股通知格式化器。"""

from __future__ import annotations

from typing import Any

from app.modules.potential.schemas import PotentialDailyResult
from app.modules.push.domain.message import NotificationMessage, NotificationSeverity
from app.modules.push.formatters.base import NotificationFormatter


def _regime_label(value: str) -> str:
    return {"bull": "多头", "bear": "空头", "neutral": "震荡"}.get(value, "震荡")


def _emotion_label(value: str) -> str:
    return {"strong": "强", "weak": "弱", "neutral": "中"}.get(value, "中")


def format_potential_stocks_feishu_card(result: PotentialDailyResult) -> dict[str, Any]:
    """格式化潜力股与题材雷达飞书卡片。"""
    stock_lines = []
    for item in result.items[:5]:
        strategies = "、".join(item.strategies) if item.strategies else "综合放量"
        chg = f"{item.change_pct:+.2f}%" if item.change_pct is not None else "-"
        industry = f" | {item.industry}" if item.industry else ""
        risk = f" | ⚠ {item.risk_flags[0]}" if item.risk_flags else ""
        fundamental = f" | 基本面 {item.fundamental_score:+.1f}" if item.fundamental_score else ""
        theme = f" | 题材 {item.themes[0]}" if item.themes else ""
        stock_lines.append(
            f"• **{item.name}** ({item.code}) 最新价 ¥{item.price or '-'} ({chg}){industry}{theme} | 换手 {item.turnover_pct or '-'}%\n"
            f"  🏷 策略: *{strategies}* | 得分: {item.score}{fundamental}{risk}"
        )
    content = "\n".join(stock_lines) if stock_lines else "今日未命中符合高分条件的标的"

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"🎯 **挖掘概况**：全市场扫描 **{result.universe_size}** 只标的，评估命中 **{len(result.items)}** 只。"
                           f"市场环境：**{_regime_label(result.market_regime)}**"
                           f" · 情绪：**{_emotion_label(result.market_emotion)}**"
                           f"{('（' + result.market_note + '）') if result.market_note else ''}\n\n"
                           f"🔥 **精选前 5 异动/潜力个股**：\n{content}",
            },
        },
    ]

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"⚡ 题材挖掘与潜力个股雷达 · {result.date}"},
            "template": "orange",
        },
        "elements": elements,
    }


def format_potential_stocks_wecom_markdown(result: PotentialDailyResult) -> str:
    """格式化潜力股与题材雷达企业微信 Markdown。"""
    stock_lines = []
    for item in result.items[:5]:
        strategies = "、".join(item.strategies) if item.strategies else "综合放量"
        chg = f"{item.change_pct:+.2f}%" if item.change_pct is not None else "-"
        industry = f" | {item.industry}" if item.industry else ""
        risk = f" | 风险: {item.risk_flags[0]}" if item.risk_flags else ""
        fundamental = f" | 基本面 {item.fundamental_score:+.1f}" if item.fundamental_score else ""
        theme = f" | 题材 {item.themes[0]}" if item.themes else ""
        stock_lines.append(
            f"- **{item.name}** ({item.code}) 最新: ¥{item.price or '-'} (<font color='info'>{chg}</font>){industry}{theme} 换手: {item.turnover_pct or '-'}%\n"
            f"  > 策略: {strategies} (得分: {item.score}){fundamental}{risk}"
        )
    content = "\n".join(stock_lines) if stock_lines else "- 今日未命中符合高分条件的标的"

    return f"""### ⚡ 题材挖掘与潜力个股雷达 · {result.date}
> 全市场扫描: **{result.universe_size}** 只 | 综合命中: **{len(result.items)}** 只 | 市场环境: **{_regime_label(result.market_regime)}** | 情绪: **{_emotion_label(result.market_emotion)}**
> {result.market_note or '按中性环境处理'}

**精选高分标的**
{content}
"""


class PotentialStocksFormatter(NotificationFormatter[PotentialDailyResult]):
    """将潜力股挖掘结果转化为标准 NotificationMessage。"""

    def format(self, payload: PotentialDailyResult) -> NotificationMessage:
        title = f"题材挖掘与潜力个股雷达 · {payload.date}"
        markdown = format_potential_stocks_wecom_markdown(payload)
        card = format_potential_stocks_feishu_card(payload)

        return NotificationMessage(
            title=title,
            summary=f"全市场扫描 {payload.universe_size} 只，命中 {len(payload.items)} 只，市场{_regime_label(payload.market_regime)}",
            markdown_body=markdown,
            severity=NotificationSeverity.INFO,
            category="potential_stocks",
            card_data=card,
            metadata={"date": payload.date, "hit_count": len(payload.items)},
        )


potential_stocks_formatter = PotentialStocksFormatter()
