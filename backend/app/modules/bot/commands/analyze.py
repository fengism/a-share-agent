"""Bot 个股分析命令。"""

import re

from app.modules.analysis.public import run_analysis
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse


class AnalyzeCommand(BotCommand):
    name = "analyze"
    aliases = ("a", "分析", "查")
    description = "分析指定 A 股"
    usage = "/analyze <6位股票代码>"
    requires_service_user = True

    def validate_args(self, args: list[str]) -> str | None:
        if not args:
            return f"请输入股票代码，用法：{self.usage}"
        if re.fullmatch(r"\d{6}", args[0]) is None:
            return "股票代码必须是 6 位数字"
        return None

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        result = await run_analysis(args[0], context.service_user_id)
        price_low, price_high = result.estimated_price_range
        risks = "\n".join(f"- {item}" for item in result.risk_warnings[:3]) or "- 暂无"
        text = (
            f"**{result.stock_code} {result.stock_name}**\n\n"
            f"- 当前价格：{result.current_price}\n"
            f"- 综合评分：{result.overall_rating}/10\n"
            f"- 操作信号：{result.signal}\n"
            f"- 置信度：{result.confidence:.0%}\n"
            f"- 目标区间：{price_low} - {price_high}\n\n"
            f"{result.overall_summary}\n\n"
            f"**风险提示**\n{risks}"
        )
        return BotResponse(text=text, title=f"股票分析 · {result.stock_name}")
