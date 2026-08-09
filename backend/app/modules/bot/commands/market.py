"""Bot 大盘复盘命令。"""

from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse
from app.modules.daily_review.public import DailyReviewRequest, generate_daily_review


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
        result = await generate_daily_review(
            DailyReviewRequest(),
            context.service_user_id,
        )
        risks = "\n".join(f"- {item}" for item in result.risk_alerts[:3]) or "- 暂无"
        opportunities = "\n".join(f"- {item}" for item in result.opportunities[:3]) or "- 暂无"
        text = (
            f"**{result.date} 市场复盘**\n\n"
            f"{result.market_summary}\n\n"
            f"**机会方向**\n{opportunities}\n\n"
            f"**风险提示**\n{risks}"
        )
        return BotResponse(text=text, title="每日大盘复盘")
