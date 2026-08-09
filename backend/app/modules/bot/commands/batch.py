"""Bot 持仓批量分析命令。"""

import asyncio
import logging

from app.modules.analysis.public import run_analysis
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse
from app.modules.portfolio.public import get_portfolio

logger = logging.getLogger(__name__)


class BatchCommand(BotCommand):
    name = "batch"
    aliases = ("b", "批量")
    description = "批量分析服务账号持仓"
    usage = "/batch"
    admin_only = True
    requires_service_user = True

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        portfolio = await get_portfolio(context.service_user_id)
        codes = [stock.stock_code for stock in portfolio.stocks]
        if not codes:
            return BotResponse(text="服务账号暂无持仓。", title="批量分析")

        selected_codes = codes[: context.batch_max_stocks]
        semaphore = asyncio.Semaphore(context.batch_concurrency)
        progress_lock = asyncio.Lock()
        completed = 0
        progress_step = max(1, (len(selected_codes) + 3) // 4)

        async def analyze(code: str) -> str:
            nonlocal completed
            try:
                async with semaphore:
                    result = await run_analysis(code, context.service_user_id)
                line = (
                    f"- `{code}` {result.stock_name}："
                    f"{result.overall_rating}/10 · {result.signal}"
                )
            except Exception:
                logger.exception("Bot 批量分析失败: code=%s", code)
                line = f"- `{code}`：分析失败"

            async with progress_lock:
                completed += 1
                if completed == len(selected_codes) or completed % progress_step == 0:
                    job_hint = f" `{context.job_id[:8]}`" if context.job_id else ""
                    await context.report_progress(
                        BotResponse(
                            text=f"任务{job_hint} 已完成 {completed}/{len(selected_codes)} 只股票。",
                            title="批量分析进度",
                        )
                    )
            return line

        lines = list(await asyncio.gather(*(analyze(code) for code in selected_codes)))
        if len(codes) > len(selected_codes):
            lines.append(
                f"- 另有 {len(codes) - len(selected_codes)} 只持仓未执行，"
                f"本次最多分析 {context.batch_max_stocks} 只"
            )
        return BotResponse(text="\n".join(lines), title="持仓批量分析")
