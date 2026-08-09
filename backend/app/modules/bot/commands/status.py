"""Bot 系统状态命令。"""

from app.configuration import get_effective_settings
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse
from app.modules.chat.public import build_capability_availability


class StatusCommand(BotCommand):
    name = "status"
    aliases = ("s", "状态", "info")
    description = "显示 Bot 与 AI 服务状态"
    usage = "/status"

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        settings = get_effective_settings()
        availability = build_capability_availability(settings)
        bot_app_id = settings.bot_feishu_app_id or settings.feishu_app_id
        bot_app_secret = settings.bot_feishu_app_secret or settings.feishu_app_secret
        feishu_ready = bool(
            settings.bot_enabled
            and bot_app_id.strip()
            and bot_app_secret.strip()
            and settings.feishu_verification_token.strip()
        )
        lines = [
            f"- Bot：{'可用' if settings.bot_enabled else '已关闭'}",
            f"- 飞书回调：{'配置完整' if feishu_ready else '配置不完整'}",
            f"- 服务账号：{'可用' if context.service_user_available else '未配置或不存在'}",
            f"- AI 服务：{availability.llm.status}",
            f"- AI 说明：{availability.llm.reason}",
            f"- 命令数量：{len(context.commands)}",
        ]
        return BotResponse(text="\n".join(lines), title="系统状态")
