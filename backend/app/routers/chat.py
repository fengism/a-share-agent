from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatStreamDelta
from app.services.chat.agent import run_chat_agent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("")
async def chat(request: ChatRequest):
    """对话端点，以 SSE 流式返回 AI 选股助手的回复增量。

    Param:
        request: ChatRequest 请求体，包含 message 和可选的历史消息列表。
    Return:
        StreamingResponse: text/event-stream 流，逐条 yield ChatStreamDelta JSON。
    """
    logger.info(
        f"Chat request: message={request.message[:50]}..., "
        f"history_len={len(request.history or [])}"
    )

    async def event_generator():
        """驱动 chat agent 并把每条增量包装为 SSE data 帧。

        Return:
            AsyncIterator[str]: SSE 格式的字节文本片段。
        """
        try:
            async for delta in run_chat_agent(request.message, request.history):
                data = json.dumps(delta.model_dump(), ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
        except Exception as e:
            logger.error(f"Chat stream error: {e}", exc_info=True)
            error_delta = ChatStreamDelta(type="error", error=str(e))
            data = json.dumps(error_delta.model_dump(), ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
