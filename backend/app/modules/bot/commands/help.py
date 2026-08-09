"""Bot 帮助命令。"""

from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse


class HelpCommand(BotCommand):
    name = "help"
    aliases = ("h", "帮助", "?")
    description = "显示命令帮助"
    usage = "/help [命令名]"

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        if args:
            requested = args[0].lower()
            command = next(
                (
                    item
                    for item in context.commands
                    if requested == item.name or requested in item.aliases
                ),
                None,
            )
            if command is None:
                return BotResponse.error(f"未知命令: {args[0]}")
            aliases = "、".join(
                f"{context.command_prefix}{alias}" if alias.isascii() else alias
                for alias in command.aliases
            )
            lines = [
                f"**{context.command_prefix}{command.name}** - {command.description}",
                f"用法：`{command.usage}`",
            ]
            if aliases:
                lines.append(f"别名：{aliases}")
            if command.admin_only:
                lines.append("权限：仅 Bot 管理员")
            return BotResponse(text="\n\n".join(lines), title="命令帮助")

        lines = ["可用命令："]
        for command in context.commands:
            admin_badge = "（管理员）" if command.admin_only else ""
            lines.append(
                f"- `{context.command_prefix}{command.name}` {command.description}{admin_badge}",
            )
        lines.append(f"\n输入 `{context.command_prefix}help <命令名>` 查看详细用法。")
        return BotResponse(text="\n".join(lines), title="股票分析助手")
