from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agentic.agents.catalog import list_agent_profiles
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.api.errors import ApiError
from app.api.streaming import SSE_RESPONSES
from app.configuration import get_effective_settings, get_settings
from app.core.concurrency.workload_limiter import ConcurrencyLimitExceeded, UserConcurrencyLimiter
from app.core.errors import log_internal_error
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.chat.agent import run_chat_agent
from app.modules.chat.availability import build_capability_availability
from app.modules.chat.schemas import (
    ChatAgentCapabilityInfo,
    ChatCapabilitiesResponse,
    ChatCapabilityAvailabilityResponse,
    ChatRequest,
    ChatSkillCapabilityInfo,
    ChatToolCapabilityInfo,
    ChatToolPolicyInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_chat_limiter = UserConcurrencyLimiter(lambda: get_settings().max_concurrent_chat_per_user)
_global_chat_limiter = UserConcurrencyLimiter(lambda: get_settings().max_concurrent_chat_total)
_GLOBAL_LIMIT_KEY = 0


@router.get("/capabilities", response_model=ChatCapabilitiesResponse)
def get_chat_capabilities() -> ChatCapabilitiesResponse:
    """返回可供当前 Chat Agent 使用的 Skill、Agent 与 Tool 公开定义。"""
    register_all_capabilities()
    skills = registry.list_skills()
    tool_to_skills: dict[str, list[str]] = {}
    for skill in skills:
        for tool_name in skill.tool_names:
            tool_to_skills.setdefault(tool_name, []).append(skill.name)

    return ChatCapabilitiesResponse(
        skills=[
            ChatSkillCapabilityInfo(
                name=skill.name,
                description=skill.description,
                triggers=list(skill.triggers),
                tool_names=list(skill.tool_names),
                rules=list(skill.rules),
                exclusions=list(skill.exclusions),
                priority=skill.priority,
            )
            for skill in skills
        ],
        agents=[
            ChatAgentCapabilityInfo(
                name=profile.name,
                display_name=profile.display_name,
                description=profile.description,
                tool_names=list(profile.tool_names),
                max_rounds=profile.max_rounds,
            )
            for profile in list_agent_profiles()
        ],
        tools=[
            ChatToolCapabilityInfo(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                policy=ChatToolPolicyInfo(
                    cost=tool.policy.cost,
                    cache_ttl_seconds=tool.policy.cache_ttl_seconds,
                    freshness=tool.policy.freshness,
                    scope=tool.policy.scope,
                ),
                skill_names=tool_to_skills.get(tool.name, []),
            )
            for tool in registry.list_tools()
        ],
        unassigned_tools=registry.validate_skill_coverage(),
    )


@router.get(
    "/capabilities/availability",
    response_model=ChatCapabilityAvailabilityResponse,
)
def get_chat_capability_availability() -> ChatCapabilityAvailabilityResponse:
    return build_capability_availability(get_effective_settings())


@router.post("", response_class=StreamingResponse, responses=SSE_RESPONSES)
async def chat(request: ChatRequest, user: AuthenticatedUser = Depends(require_active_user)):
    """对话端点，以 SSE 流式返回 AI 选股助手的回复增量。

    Param:
        request: ChatRequest 请求体，包含 message 和可选的历史消息列表。
    Return:
        StreamingResponse: text/event-stream 流，逐条 yield AgentEvent JSON。
    """
    logger.info(
        "Chat request: user_id=%s, message_length=%s, history_len=%s",
        user["id"],
        len(request.message),
        len(request.history or []),
    )
    leases = []
    try:
        leases.append(await _global_chat_limiter.acquire(_GLOBAL_LIMIT_KEY))
        leases.append(await _chat_limiter.acquire(user["id"]))
    except ConcurrencyLimitExceeded as exc:
        for acquired_lease in reversed(leases):
            await acquired_lease.release()
        raise ApiError(
            status_code=429,
            code="chat.concurrency_limit",
            message="当前对话任务较多，请等待已有回复完成后重试",
            headers={"Retry-After": "5"},
        ) from exc

    async def event_generator():
        """驱动 chat agent 并把每条增量包装为 SSE data 帧。

        Return:
            AsyncIterator[str]: SSE 格式的字节文本片段。
        """
        queue: asyncio.Queue[AgentEvent | object] = asyncio.Queue(maxsize=100)
        completed = object()

        async def produce() -> None:
            try:
                timeout_seconds = max(1, int(get_settings().chat_total_timeout_seconds))
                async with asyncio.timeout(timeout_seconds):
                    async for delta in run_chat_agent(
                        request.message,
                        request.history,
                        request.agent_names,
                        request.skill_names,
                    ):
                        await queue.put(delta)
            except TimeoutError:
                await queue.put(AgentEvent(type="error", error="对话处理超时，请缩小问题范围后重试"))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _, detail = log_internal_error(
                    logger,
                    "Chat 流式响应",
                    exc,
                    "对话服务暂时不可用，请稍后重试",
                )
                await queue.put(AgentEvent(type="error", error=detail))
            finally:
                try:
                    queue.put_nowait(completed)
                except asyncio.QueueFull:
                    pass

        producer = asyncio.create_task(produce())

        heartbeat_seconds = max(1, int(get_settings().chat_heartbeat_seconds))
        try:
            while True:
                if producer.done() and queue.empty():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                except TimeoutError:
                    if producer.done() and queue.empty():
                        break
                    yield ": ping\n\n"
                    continue
                if item is completed:
                    break
                data = json.dumps(item.model_dump(), ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
            for acquired_lease in reversed(leases):
                await asyncio.shield(acquired_lease.release())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
