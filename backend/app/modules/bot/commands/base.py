"""Bot 命令抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse


class BotCommand(ABC):
    name: str
    aliases: tuple[str, ...] = ()
    description: str
    usage: str
    admin_only = False
    requires_service_user = False

    def validate_args(self, args: list[str]) -> str | None:
        return None

    @abstractmethod
    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        raise NotImplementedError
