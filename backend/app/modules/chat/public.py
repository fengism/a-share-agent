"""Chat 模块对 HTTP 和其他业务适配器开放的稳定入口。"""

from app.modules.chat.availability import build_capability_availability
from app.modules.chat.capabilities import build_chat_capabilities, load_chat_capability_availability
from app.modules.chat.schemas import (
    ChatCapabilitiesResponse,
    ChatCapabilityAvailabilityResponse,
    ChatRequest,
    ChatStateResponse,
    ChatStateSnapshot,
)
from app.modules.chat.state_service import ChatStateConflictError, get_chat_state, save_chat_state
from app.modules.chat.stream_service import ChatConcurrencyLimitError, start_chat_stream

__all__ = [
    "ChatCapabilitiesResponse",
    "ChatCapabilityAvailabilityResponse",
    "ChatConcurrencyLimitError",
    "ChatRequest",
    "ChatStateResponse",
    "ChatStateSnapshot",
    "ChatStateConflictError",
    "build_capability_availability",
    "build_chat_capabilities",
    "load_chat_capability_availability",
    "get_chat_state",
    "save_chat_state",
    "start_chat_stream",
]
