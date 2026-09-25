"""Compatibility facade: agents and standalone generation share one transport."""
from app.infrastructure.llm.completion import create_chat_completion, stream_chat_completion

__all__ = ["create_chat_completion", "stream_chat_completion"]
