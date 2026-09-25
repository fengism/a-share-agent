"""Chat 流式执行的应用服务。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from dataclasses import dataclass

from app.agentic.events import AgentEvent
from app.configuration import get_settings
from app.configuration.schema import Settings
from app.core.concurrency.workload_limiter import (
    ConcurrencyLimitExceeded,
    UserConcurrencyLease,
    UserConcurrencyLimiter,
)
from app.core.errors import log_internal_error
from app.modules.chat.agent import run_chat_agent
from app.modules.chat.schemas import ChatRequest

logger = logging.getLogger(__name__)

_GLOBAL_LIMIT_KEY = 0
ChatAgentRunner = Callable[..., AsyncGenerator[AgentEvent, None]]


class ChatConcurrencyLimitError(RuntimeError):
    """Chat 的全局或用户级并发额度已耗尽。"""


@dataclass(frozen=True)
class ChatStreamUpdate:
    agent_event: AgentEvent | None = None
    heartbeat: bool = False


class ChatStreamSession:
    """持有一次 Chat 流及其并发额度。"""

    def __init__(
        self,
        updates: AsyncGenerator[ChatStreamUpdate, None],
        leases: list[UserConcurrencyLease],
    ) -> None:
        self._updates = updates
        self._leases = leases
        self._closed = False

    def __aiter__(self) -> ChatStreamSession:
        return self

    async def __anext__(self) -> ChatStreamUpdate:
        if self._closed:
            raise StopAsyncIteration
        try:
            return await anext(self._updates)
        except StopAsyncIteration:
            await self.aclose()
            raise
        except BaseException:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._updates.aclose()
        finally:
            for lease in reversed(self._leases):
                await asyncio.shield(lease.release())


class ChatStreamService:
    def __init__(
        self,
        *,
        settings_loader: Callable[[], Settings] = get_settings,
        agent_runner: ChatAgentRunner = run_chat_agent,
        user_limiter: UserConcurrencyLimiter | None = None,
        global_limiter: UserConcurrencyLimiter | None = None,
    ) -> None:
        self._settings_loader = settings_loader
        self._agent_runner = agent_runner
        self._user_limiter = user_limiter or UserConcurrencyLimiter(
            lambda: self._settings_loader().max_concurrent_chat_per_user
        )
        self._global_limiter = global_limiter or UserConcurrencyLimiter(
            lambda: self._settings_loader().max_concurrent_chat_total
        )

    async def start(self, request: ChatRequest, *, user_id: int) -> ChatStreamSession:
        logger.info(
            "Chat request: user_id=%s, message_length=%s, history_len=%s",
            user_id,
            len(request.message),
            len(request.history or []),
        )
        leases: list[UserConcurrencyLease] = []
        try:
            leases.append(await self._global_limiter.acquire(_GLOBAL_LIMIT_KEY))
            leases.append(await self._user_limiter.acquire(user_id))
        except BaseException as error:
            for lease in reversed(leases):
                await asyncio.shield(lease.release())
            if isinstance(error, ConcurrencyLimitExceeded):
                raise ChatConcurrencyLimitError from error
            raise

        settings = self._settings_loader()
        updates = self._stream_updates(request, settings)
        return ChatStreamSession(updates, leases)

    async def _stream_updates(
        self,
        request: ChatRequest,
        settings: Settings,
    ) -> AsyncGenerator[ChatStreamUpdate, None]:
        queue: asyncio.Queue[AgentEvent | object] = asyncio.Queue(maxsize=100)
        completed = object()

        async def produce() -> None:
            try:
                timeout_seconds = max(1, int(settings.chat_total_timeout_seconds))
                async with asyncio.timeout(timeout_seconds):
                    async with aclosing(self._agent_runner(
                        request.message,
                        request.history,
                        request.agent_names,
                        request.skill_names,
                    )) as stream:
                        async for event in stream:
                            await queue.put(event)
            except TimeoutError:
                await queue.put(AgentEvent(type="error", error="对话处理超时，请缩小问题范围后重试"))
            except asyncio.CancelledError:
                raise
            except Exception as error:
                _, detail = log_internal_error(
                    logger,
                    "Chat 流式响应",
                    error,
                    "对话服务暂时不可用，请稍后重试",
                )
                await queue.put(AgentEvent(type="error", error=detail))
            finally:
                try:
                    queue.put_nowait(completed)
                except asyncio.QueueFull:
                    pass

        producer = asyncio.create_task(produce())
        heartbeat_seconds = max(1, int(settings.chat_heartbeat_seconds))
        try:
            while True:
                if producer.done() and queue.empty():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                except TimeoutError:
                    if producer.done() and queue.empty():
                        break
                    yield ChatStreamUpdate(heartbeat=True)
                    continue
                if item is completed:
                    break
                if isinstance(item, AgentEvent):
                    yield ChatStreamUpdate(agent_event=item)
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)


chat_stream_service = ChatStreamService()


async def start_chat_stream(request: ChatRequest, *, user_id: int) -> ChatStreamSession:
    return await chat_stream_service.start(request, user_id=user_id)
