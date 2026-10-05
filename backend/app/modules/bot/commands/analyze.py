"""Bot 个股分析命令。"""

import re

from app.core.market import STOCK_CODE_PATH_PATTERN
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.public import run_analysis
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse

_NEW_INVESTOR_LABELS = {
    "buy": "买入",
    "watch": "关注",
    "avoid": "回避",
}


def _format_range(value: tuple[float, float] | None) -> str | None:
    if value is None or len(value) != 2:
        return None
    return f"{value[0]:.2f} - {value[1]:.2f}"


def _format_analysis_result(result: AnalysisResult) -> str:
    """把完整研究结果整理为卡片文本；缺少的研究维度自动省略。"""
    framework = result.research_framework
    actions = framework.actions if framework else None
    scenarios = framework.valuation.scenarios if framework and framework.valuation else None

    lines: list[str] = [
        f"**{result.stock_code} {result.stock_name}**",
        f"综合评分 {result.overall_rating}/10 ｜ 信号 {result.signal} ｜ 置信度 {result.confidence:.0%}",
        "",
        "**核心结论**",
        result.overall_summary,
        "",
        "**估值与操作**",
        f"- 当前价格：{result.current_price:.2f}",
    ]
    estimated = _format_range(result.estimated_price_range)
    if estimated:
        lines.append(f"- 综合目标区间：{estimated}")
    buy_range = _format_range(actions.buy_or_add_range) if actions else None
    if buy_range:
        lines.append(f"- 建议买入/加仓区间：{buy_range}")
    if scenarios:
        for label, scenario in (("悲观", scenarios.bear), ("基准", scenarios.base), ("乐观", scenarios.bull)):
            fair = _format_range(scenario.fair_value_range)
            if fair:
                lines.append(f"- {label}情景区间：{fair}")
    if framework and framework.valuation and framework.valuation.margin_of_safety:
        lines.append(f"- 安全边际：{framework.valuation.margin_of_safety}")
    if actions and actions.new_investor_action != "insufficient_evidence":
        label = _NEW_INVESTOR_LABELS.get(actions.new_investor_action)
        if label:
            lines.append(f"- 新资金建议：{label}")

    key_factors = [item for item in result.key_factors if item]
    if key_factors:
        lines += ["", "**关键因子**"] + [f"- {item}" for item in key_factors[:4]]

    thesis_breakers = [item for item in (actions.thesis_breakers if actions else []) if item]
    if thesis_breakers:
        lines += ["", "**观点失效条件**"] + [f"- {item}" for item in thesis_breakers[:3]]

    risks = [item for item in result.risk_warnings if item] or ["暂无"]
    lines += ["", "**风险提示**"] + [f"- {item}" for item in risks[:5]]
    return "\n".join(lines)


class AnalyzeCommand(BotCommand):
    name = "analyze"
    aliases = ("a", "分析", "查")
    description = "分析指定 A 股或港股"
    usage = "/analyze <股票代码>"
    requires_service_user = True

    def validate_args(self, args: list[str]) -> str | None:
        if not args:
            return f"请输入股票代码，用法：{self.usage}"
        if re.fullmatch(STOCK_CODE_PATH_PATTERN, args[0], re.IGNORECASE) is None:
            return "股票代码必须是 6 位 A 股代码或 1-5 位港股代码"
        return None

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        # 完整分析流水线耗时较长，先发受理回执避免用户等待期间无反馈
        await context.report_progress(BotResponse(
            text=f"已开始分析 {args[0]}，完整研判需要 1-3 分钟，完成后自动回复结果。",
            title=f"股票分析 · {args[0]}",
        ))
        result = await run_analysis(args[0], context.service_user_id)
        return BotResponse(
            text=_format_analysis_result(result),
            title=f"股票分析 · {result.stock_name}",
        )
