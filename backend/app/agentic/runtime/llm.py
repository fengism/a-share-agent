"""Transport port for LLM chat completions.

The core agent runtime depends only on this module. The host application wires
concrete implementations (OpenAI/LiteLLM/etc.) through ``configure_llm_transport``
at composition time, so the agentic package does not import infrastructure.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

CreateChatCompletion = Callable[..., Awaitable[Any]]
StreamChatCompletion = Callable[..., AsyncGenerator[Any, None]]

_create_chat_completion: CreateChatCompletion | None = None
_stream_chat_completion: StreamChatCompletion | None = None


def configure_llm_transport(
    create: CreateChatCompletion,
    stream: StreamChatCompletion,
) -> None:
    """Install the host's concrete transport. Idempotent; last writer wins."""
    global _create_chat_completion, _stream_chat_completion
    _create_chat_completion = create
    _stream_chat_completion = stream


def _transport_missing() -> RuntimeError:
    return RuntimeError(
        "Agentic LLM transport 尚未配置；请在组合根调用 "
        "app.agentic.runtime.llm.configure_llm_transport()"
    )


async def create_chat_completion(client: Any, **kwargs: Any) -> Any:
    if _create_chat_completion is None:
        raise _transport_missing()
    return await _create_chat_completion(client, **kwargs)


def stream_chat_completion(client: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
    if _stream_chat_completion is None:
        raise _transport_missing()
    return _stream_chat_completion(client, **kwargs)


__all__ = [
    "configure_llm_transport",
    "create_chat_completion",
    "stream_chat_completion",
]
