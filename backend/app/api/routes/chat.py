"""Chat HTTP API。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agentic.events import auditable_agent_event
from app.api.auth.dependencies import require_active_user
from app.api.errors import ApiError, ConflictError
from app.api.rate_limit import llm_rate_limit
from app.api.streaming import SSE_RESPONSES
from app.domain.identity import AuthenticatedUser
from app.modules.chat.public import (
    ChatCapabilitiesResponse,
    ChatCapabilityAvailabilityResponse,
    ChatConcurrencyLimitError,
    ChatRequest,
    ChatStateConflictError,
    ChatStateResponse,
    ChatStateSnapshot,
    build_chat_capabilities,
    get_chat_state,
    load_chat_capability_availability,
    save_chat_state,
    start_chat_stream,
)

router = APIRouter()


@router.get("/sessions", response_model=ChatStateResponse)
async def read_chat_sessions(user: AuthenticatedUser = Depends(require_active_user)):
    return await get_chat_state(user["id"])


@router.put("/sessions", response_model=ChatStateResponse)
async def write_chat_sessions(
    state: ChatStateSnapshot,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await save_chat_state(state, user["id"])
    except ChatStateConflictError as error:
        raise ConflictError(
            "聊天会话已在其他页面更新，已重新加载最新内容",
            code="chat.state_conflict",
        ) from error


@router.get("/capabilities", response_model=ChatCapabilitiesResponse)
def get_chat_capabilities() -> ChatCapabilitiesResponse:
    """返回可供当前 Chat Agent 使用的 Skill、Agent 与 Tool 公开定义。"""
    return build_chat_capabilities()


@router.get(
    "/capabilities/availability",
    response_model=ChatCapabilityAvailabilityResponse,
)
def get_chat_capability_availability() -> ChatCapabilityAvailabilityResponse:
    return load_chat_capability_availability()


@router.post(
    "",
    response_class=StreamingResponse,
    responses=SSE_RESPONSES,
    dependencies=[Depends(llm_rate_limit)],
)
async def chat(request: ChatRequest, user: AuthenticatedUser = Depends(require_active_user)):
    """对话端点，以 SSE 流式返回 AI 选股助手的回复增量。

    Param:
        request: ChatRequest 请求体，包含 message 和可选的历史消息列表。
    Return:
        StreamingResponse: text/event-stream 流，逐条 yield AgentEvent JSON。
    """
    try:
        session = await start_chat_stream(request, user_id=user["id"])
    except ChatConcurrencyLimitError as error:
        raise ApiError(
            status_code=429,
            code="chat.concurrency_limit",
            message="当前对话任务较多，请等待已有回复完成后重试",
            headers={"Retry-After": "5"},
        ) from error

    async def event_generator():
        """把 Chat 应用事件转换为 SSE 帧。

        Return:
            AsyncIterator[str]: SSE 格式的字节文本片段。
        """
        try:
            async for update in session:
                if update.heartbeat:
                    yield ": ping\n\n"
                    continue
                if update.agent_event is None:
                    continue
                public_event = auditable_agent_event(
                    update.agent_event,
                    include_text=True,
                    include_reasoning=True,
                    strip_tool_content=False,
                )
                if public_event is None:
                    continue
                data = json.dumps(public_event.model_dump(), ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
        finally:
            await session.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
