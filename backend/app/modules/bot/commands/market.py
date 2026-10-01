"""Bot 大盘复盘命令。"""

from app.domain.content import ContentBlock
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse
from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult
from app.modules.daily_review.public import DailyReviewRequest, generate_daily_review
from app.modules.push.content import _STATE_LABELS, _build_daily_review_data_blocks

_DATA_SECTION_HEADINGS = ("主要指数表现", "量能与市场宽度", "短线连板天梯", "行业板块涨跌榜")
_SUMMARY_CHAR_LIMIT = 600
_REPLY_CHAR_BUDGET = 2900


def _blocks_to_text(blocks: list[ContentBlock]) -> str:
    lines: list[str] = []
    for block in blocks:
        if not block.text:
            continue
        if block.type == "heading":
            lines.append(f"**{block.text}**")
        elif block.type == "bullet":
            lines.append(f"- {block.text}")
        else:
            lines.append(block.text)
    return "\n".join(lines)


def _data_section_text(snapshot: DailyReviewDataSnapshot, char_budget: int) -> str:
    """摘取共享推送内容块里的大盘数据要点，避免再维护一份重复的格式逻辑。"""
    selected: list[ContentBlock] = []
    keeping = False
    used = 0
    for block in _build_daily_review_data_blocks(snapshot):
        if block.type == "heading":
            keeping = any(name in block.text for name in _DATA_SECTION_HEADINGS)
            if keeping:
                selected.append(block)
            continue
        if keeping and block.text:
            if used + len(block.text) > char_budget:
                selected.append(ContentBlock(type="paragraph", text="…"))
                break
            used += len(block.text)
            selected.append(block)
    return _blocks_to_text(selected)


def _trimmed(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else f"{text[:limit]}…"


def _format_market_reply(result: DailyReviewResult) -> str:
    state_label = _STATE_LABELS.get(result.market_state, "数据不足")
    header = (
        f"📅 {result.effective_date or result.date} 市场复盘"
        f"（{state_label} ｜ 建议仓位 {result.position_range or '灵活配置'}）"
    )
    opportunities = [item for item in (result.opportunities or []) if item] or ["暂无"]
    risks = [item for item in (result.risk_alerts or []) if item] or ["暂无"]
    events = [impact for impact in result.event_impacts if impact.event_title]
    head_text = "\n".join([
        header,
        "",
        _trimmed(result.market_summary, _SUMMARY_CHAR_LIMIT),
        "",
        "**机会方向**",
        *[f"- {item}" for item in opportunities[:3]],
        "**风险提示**",
        *[f"- {item}" for item in risks[:3]],
        "**政策与事件影响**",
        *(
            [
                f"- {impact.event_title}：{impact.transmission_chain or '待盘面确认'}"
                for impact in events[:2]
            ]
            or ["- 暂无可核验的重点政策事件"]
        ),
    ])
    remaining = _REPLY_CHAR_BUDGET - len(head_text) - 40
    parts: list[str] = [head_text]
    if remaining > 200 and result.data_snapshot:
        data_text = _data_section_text(result.data_snapshot, char_budget=remaining)
        if data_text:
            parts += ["", "**📊 数据看板**", data_text]
    return "\n".join(parts)


class MarketCommand(BotCommand):
    name = "market"
    aliases = ("m", "大盘", "复盘")
    description = "生成当日大盘复盘"
    usage = "/market"
    requires_service_user = True

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        await context.report_progress(BotResponse(
            text="正在获取当日复盘；若今日尚未生成过，需要 1-3 分钟，完成后自动回复。",
            title="每日大盘复盘",
        ))
        result = await generate_daily_review(
            DailyReviewRequest(),
            context.service_user_id,
        )
        return BotResponse(
            text=_format_market_reply(result),
            title=f"{result.date} 市场复盘",
        )
