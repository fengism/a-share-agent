"""Bot 命令运行时装配。"""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable

from app.configuration import get_settings
from app.configuration.schema import Settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.request_context import reset_current_user, set_current_user
from app.infrastructure.persistence import account_store
from app.modules.bot.commands import (
    AnalyzeCommand,
    BatchCommand,
    HelpCommand,
    MarketCommand,
    StatusCommand,
    TaskCommand,
)
from app.modules.bot.dispatcher import CommandDispatcher
from app.modules.bot.models import BotMessage, BotResponse
from app.modules.bot.persistence import rate_limits as rate_limit_store


class BotService:
    def __init__(self, settings: Settings) -> None:
        self._service_user_id = settings.bot_service_user_id
        self._rate_limit_requests = settings.bot_rate_limit_requests
        self._rate_limit_window = settings.bot_rate_limit_window
        self._batch_concurrency = min(8, max(1, settings.bot_batch_concurrency))
        self._batch_max_stocks = min(50, max(1, settings.bot_batch_max_stocks))
        self._dispatcher = CommandDispatcher(
            command_prefix=settings.bot_command_prefix,
            rate_limit_requests=settings.bot_rate_limit_requests,
            rate_limit_window=settings.bot_rate_limit_window,
            admin_users=settings.bot_admin_users,
            rate_limit_checker=self._allow_request,
        )
        for command in (
            HelpCommand(),
            StatusCommand(),
            TaskCommand(),
            AnalyzeCommand(),
            MarketCommand(),
            BatchCommand(),
        ):
            self._dispatcher.register(command)

    async def _allow_request(self, scope_key: str) -> bool:
        return await call_blocking(
            rate_limit_store.allow,
            scope_key,
            self._rate_limit_requests,
            self._rate_limit_window,
            semaphore=database_semaphore,
        )
    async def dispatch(
        self,
        message: BotMessage,
        *,
        job_id: str = "",
        progress_reporter: Callable[[BotResponse], Awaitable[None]] | None = None,
    ) -> BotResponse | None:
        service_user = (
            await call_blocking(
                account_store.get_user_by_id,
                self._service_user_id,
                semaphore=database_semaphore,
            )
            if self._service_user_id > 0
            else None
        )
        reset_token = set_current_user(service_user) if service_user is not None else None
        try:
            return await self._dispatcher.dispatch(
                message,
                service_user_id=self._service_user_id,
                service_user_available=service_user is not None,
                job_id=job_id,
                batch_concurrency=self._batch_concurrency,
                batch_max_stocks=self._batch_max_stocks,
                progress_reporter=progress_reporter,
            )
        finally:
            if reset_token is not None:
                reset_current_user(reset_token)


_service: BotService | None = None
_service_signature: tuple | None = None
_service_lock = threading.Lock()


def _settings_signature(settings: Settings) -> tuple:
    return (
        settings.bot_command_prefix,
        settings.bot_service_user_id,
        settings.bot_rate_limit_requests,
        settings.bot_rate_limit_window,
        tuple(settings.bot_admin_users),
        settings.bot_batch_concurrency,
        settings.bot_batch_max_stocks,
    )


def get_bot_service() -> BotService:
    global _service, _service_signature
    settings = get_settings()
    signature = _settings_signature(settings)
    with _service_lock:
        if _service is None or _service_signature != signature:
            _service = BotService(settings)
            _service_signature = signature
        return _service


def reset_bot_service() -> None:
    global _service, _service_signature
    with _service_lock:
        _service = None
        _service_signature = None
