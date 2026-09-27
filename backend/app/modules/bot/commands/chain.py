"""Bot 产业链存档查询命令。"""

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.public import (
    get_latest_industry_chain_archive,
    load_industry_chain,
)

_THESIS_DETAIL_LIMIT = 120
_REPLY_CHAR_BUDGET = 2900


def _trimmed(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else f"{text[:limit]}…"


def _format_chain_reply(result: IndustryChainResult) -> str:
    lines: list[str] = [f"**{result.name or '产业链分析'}**"]
    positioning = _trimmed(result.positioning, 300)
    if positioning:
        lines += ["", "**产业链定位**", positioning]

    theses = [t for t in result.research_theses if t.title]
    if theses:
        lines += ["", "**核心研究论点**"]
        for thesis in theses[:3]:
            detail = _trimmed(thesis.detail, _THESIS_DETAIL_LIMIT)
            lines.append(f"- {thesis.title}" + (f"：{detail}" if detail else ""))

    opportunities = [item for item in result.opportunities if item.name]
    if opportunities:
        lines += ["", "**机会方向（按综合评分）**"]
        for item in sorted(opportunities, key=lambda o: o.total_score, reverse=True)[:3]:
            code = f" {item.code}" if item.code else ""
            role = f" ｜ {item.role}" if item.role else ""
            score = f" ｜ 综合 {item.total_score}" if item.total_score else ""
            lines.append(f"- {item.name}{code}{role}{score}")

    risks = [item for item in result.risks if item]
    if risks:
        lines += ["", "**风险提示**"] + [f"- {_trimmed(item, 120)}" for item in risks[:3]]

    stocks = [item for item in result.key_stocks if (item.name or item.company or item.code)]
    if stocks:
        lines += ["", "**关键公司**"]
        for node in stocks[:5]:
            name = node.name or node.company or node.code
            code = f"（{node.code}）" if node.code and node.code != name else ""
            lines.append(f"- {name}{code}")

    return "\n".join(lines)[:_REPLY_CHAR_BUDGET]


class ChainCommand(BotCommand):
    name = "chain"
    aliases = ("c", "产业链")
    description = "查看产业链最新存档摘要"
    usage = "/chain <产业链名称>"
    requires_service_user = True

    def validate_args(self, args: list[str]) -> str | None:
        if not args:
            return f"请输入产业链名称，用法：{self.usage}"
        return None

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        name = args[0]
        latest = await get_latest_industry_chain_archive(
            name,
            context.service_user_id,
            can_delete_legacy=False,
        )
        if not latest.archive_id:
            return BotResponse.error(
                f"暂无「{name}」的产业链分析存档，请先在网页端生成并保存后再来查询。",
            )
        # load_industry_chain 是同步文件读取，必须放到线程池执行
        result = await call_blocking(
            load_industry_chain,
            name,
            latest.archive_id,
            context.service_user_id,
            semaphore=misc_semaphore,
        )
        if result is None:
            return BotResponse.error("存档读取失败，请稍后重试或在网页端重新生成。")
        return BotResponse(
            text=_format_chain_reply(result),
            title=f"产业链分析 · {result.name or name}",
        )
