"""Compatibility facade for provider-neutral LLM tool-calling contracts.

The implementation lives in :mod:`app.domain.agent_llm` so the agent runtime can
use it without importing infrastructure. Existing infrastructure callers keep
importing this module.
"""

from __future__ import annotations

from app.domain.agent_llm import (
    DEFAULT_LLM_CAPABILITIES as DEFAULT_LLM_CAPABILITIES,
)
from app.domain.agent_llm import (
    AsyncChatAPI as AsyncChatAPI,
)
from app.domain.agent_llm import (
    AsyncChatCompletions as AsyncChatCompletions,
)
from app.domain.agent_llm import (
    AsyncLLMClient as AsyncLLMClient,
)
from app.domain.agent_llm import (
    ChatCompletionStreamNormalizer as ChatCompletionStreamNormalizer,
)
from app.domain.agent_llm import (
    LLMCapabilities as LLMCapabilities,
)
from app.domain.agent_llm import (
    LLMStreamDelta as LLMStreamDelta,
)
from app.domain.agent_llm import (
    LLMTurn as LLMTurn,
)
from app.domain.agent_llm import (
    ToolChoice as ToolChoice,
)
from app.domain.agent_llm import (
    ToolRequest as ToolRequest,
)
from app.domain.agent_llm import (
    capabilities_from_client as capabilities_from_client,
)
from app.domain.agent_llm import (
    normalize_chat_completion as normalize_chat_completion,
)
from app.domain.agent_llm import (
    normalize_tool_arguments as normalize_tool_arguments,
)
from app.domain.agent_llm import (
    resolve_tool_request as resolve_tool_request,
)
from app.infrastructure.llm.capabilities import (
    resolve_llm_capabilities as resolve_llm_capabilities,
)

__all__ = [
    "AsyncChatAPI",
    "AsyncChatCompletions",
    "AsyncLLMClient",
    "ChatCompletionStreamNormalizer",
    "DEFAULT_LLM_CAPABILITIES",
    "LLMCapabilities",
    "LLMStreamDelta",
    "LLMTurn",
    "ToolChoice",
    "ToolRequest",
    "capabilities_from_client",
    "normalize_chat_completion",
    "normalize_tool_arguments",
    "resolve_llm_capabilities",
    "resolve_tool_request",
]
