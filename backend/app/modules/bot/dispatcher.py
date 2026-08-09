"""Bot 命令注册、解析与分发。"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from app.core.metrics import metrics
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotCommandInfo, BotExecutionContext, BotMessage, BotResponse

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_requests = max(1, max_requests)
        self._window_seconds = max(1, window_seconds)
        self._clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        window_start = now - self._window_seconds
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= window_start:
                requests.popleft()
            if len(requests) >= self._max_requests:
                return False
            requests.append(now)
            return True


class CommandDispatcher:
    def __init__(
        self,
        *,
        command_prefix: str = "/",
        rate_limit_requests: int = 10,
        rate_limit_window: int = 60,
        admin_users: list[str] | None = None,
        rate_limit_checker: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self.command_prefix = command_prefix or "/"
        self._commands: dict[str, BotCommand] = {}
        self._aliases: dict[str, str] = {}
        self._admin_users = set(admin_users or [])
        self._rate_limit_checker = rate_limit_checker
        self._rate_limiter = (
            SlidingWindowRateLimiter(
                rate_limit_requests,
                rate_limit_window,
            )
            if rate_limit_checker is None
            else None
        )

    def register(self, command: BotCommand) -> None:
        name = command.name.strip().lower()
        if not name:
            raise ValueError("Bot 命令名称不能为空")
        if name in self._commands or name in self._aliases:
            raise ValueError(f"Bot 命令名称重复: {name}")
        aliases = tuple(alias.strip().lower() for alias in command.aliases if alias.strip())
        collisions = sorted(alias for alias in aliases if alias in self._commands or alias in self._aliases)
        if collisions:
            raise ValueError(f"Bot 命令别名重复: {', '.join(collisions)}")
        self._commands[name] = command
        self._aliases.update({alias: name for alias in aliases})

    def list_commands(self) -> tuple[BotCommandInfo, ...]:
        return tuple(
            BotCommandInfo(
                name=command.name,
                aliases=command.aliases,
                description=command.description,
                usage=command.usage,
                admin_only=command.admin_only,
            )
            for command in self._commands.values()
        )

    def _parse(self, content: str) -> tuple[str, list[str]] | None:
        text = content.strip()
        if not text:
            return None
        if text.startswith(self.command_prefix):
            parts = text[len(self.command_prefix):].strip().split()
            return (parts[0].lower(), parts[1:]) if parts else None

        token, _, remainder = text.partition(" ")
        normalized_token = token.lower()
        if normalized_token in self._commands or normalized_token in self._aliases:
            return normalized_token, remainder.split() if remainder else []

        chinese_aliases = sorted(
            (alias for alias in self._aliases if not alias.isascii()),
            key=len,
            reverse=True,
        )
        for alias in chinese_aliases:
            if text.startswith(alias):
                return alias, text[len(alias):].strip().split()
        return None

    def resolve(self, message: BotMessage) -> tuple[BotCommand | None, list[str]] | None:
        parsed = self._parse(message.content)
        if parsed is None:
            return None
        name, args = parsed
        canonical_name = self._aliases.get(name, name)
        return self._commands.get(canonical_name), args

    async def dispatch(
        self,
        message: BotMessage,
        *,
        service_user_id: int,
        service_user_available: bool,
        job_id: str = "",
        batch_concurrency: int = 2,
        batch_max_stocks: int = 10,
        progress_reporter: Callable[[BotResponse], Awaitable[None]] | None = None,
    ) -> BotResponse | None:
        resolved = self.resolve(message)
        if resolved is None:
            return None
        command, args = resolved
        if command is None:
            return BotResponse.error(
                f"未知命令，请输入 {self.command_prefix}help 查看帮助",
            )
        rate_limit_key = f"{message.platform}:{message.user_id}"
        allowed = (
            await self._rate_limit_checker(rate_limit_key)
            if self._rate_limit_checker is not None
            else self._rate_limiter is not None and self._rate_limiter.allow(rate_limit_key)
        )
        if not allowed:
            metrics.record_bot_event("rate_limited")
            return BotResponse.error("请求过于频繁，请稍后再试")
        if command.admin_only and message.user_id not in self._admin_users:
            return BotResponse.error("该命令仅限 Bot 管理员使用")
        if command.requires_service_user and not service_user_available:
            return BotResponse.error("BOT_SERVICE_USER_ID 未配置或对应账号不存在")
        validation_error = command.validate_args(args)
        if validation_error:
            return BotResponse.error(validation_error)

        context = BotExecutionContext(
            service_user_id=service_user_id,
            service_user_available=service_user_available,
            command_prefix=self.command_prefix,
            commands=self.list_commands(),
            job_id=job_id,
            batch_concurrency=max(1, batch_concurrency),
            batch_max_stocks=max(1, batch_max_stocks),
            progress_reporter=progress_reporter,
        )
        started_at = time.perf_counter()
        try:
            response = await command.execute(message, args, context)
        except Exception as exc:
            metrics.record_bot_command(
                command.name,
                success=False,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error_type=type(exc).__name__,
            )
            logger.exception(
                "Bot 命令执行失败: platform=%s user=%s command=%s",
                message.platform,
                message.user_id,
                command.name,
            )
            return BotResponse.error("命令执行失败，请稍后重试")
        metrics.record_bot_command(
            command.name,
            success=True,
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )
        return response
