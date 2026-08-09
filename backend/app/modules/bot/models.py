"""Bot Command 统一消息与响应模型。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class BotMessage:
    platform: str
    message_id: str
    event_id: str
    user_id: str
    user_name: str
    chat_id: str
    chat_type: Literal["group", "private", "unknown"]
    content: str
    mentioned: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BotResponse:
    text: str
    title: str = "股票分析助手"
    markdown: bool = True

    @classmethod
    def error(cls, message: str) -> "BotResponse":
        return cls(text=f"❌ {message}", title="命令执行失败", markdown=False)


@dataclass(frozen=True, slots=True)
class BotCommandInfo:
    name: str
    aliases: tuple[str, ...]
    description: str
    usage: str
    admin_only: bool


@dataclass(frozen=True, slots=True)
class BotExecutionContext:
    service_user_id: int
    service_user_available: bool
    command_prefix: str
    commands: tuple[BotCommandInfo, ...]
    job_id: str = ""
    batch_concurrency: int = 2
    batch_max_stocks: int = 10
    progress_reporter: Callable[[BotResponse], Awaitable[None]] | None = None

    async def report_progress(self, response: BotResponse) -> None:
        if self.progress_reporter is not None:
            await self.progress_reporter(response)
