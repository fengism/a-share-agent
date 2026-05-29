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
    logger.info(
        f"Chat request: message={request.message[:50]}..., "
        f"history_len={len(request.history or [])}"
    )

    async def event_generator():
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
