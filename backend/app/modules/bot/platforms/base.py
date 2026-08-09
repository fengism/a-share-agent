"""Bot 平台适配器抽象。"""

from abc import ABC, abstractmethod

from app.modules.bot.models import BotMessage, BotResponse


class BotPlatform(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def send_response(self, message: BotMessage, response: BotResponse) -> None:
        raise NotImplementedError
