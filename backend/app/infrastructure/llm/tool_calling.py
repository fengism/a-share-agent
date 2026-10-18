"""Provider-neutral contracts and normalization for LLM tool calling."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.domain.agent_protocol import ToolCallFunction, ToolCallInfo
from app.infrastructure.llm.adapters import extract_message_text
from app.infrastructure.llm.capabilities import (
    DEFAULT_LLM_CAPABILITIES as DEFAULT_LLM_CAPABILITIES,
)
from app.infrastructure.llm.capabilities import (
    LLMCapabilities as LLMCapabilities,
)
from app.infrastructure.llm.capabilities import (
    resolve_llm_capabilities as resolve_llm_capabilities,
)

ToolChoice = Literal["auto", "required", "none"]


class AsyncChatCompletions(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class AsyncChatAPI(Protocol):
    completions: AsyncChatCompletions


class AsyncLLMClient(Protocol):
    """Small structural interface required by the agent runtime."""

    chat: AsyncChatAPI


@dataclass(frozen=True, slots=True)
class LLMTurn:
    content: str
    reasoning_content: str
    tool_calls: tuple[ToolCallInfo, ...]
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class LLMStreamDelta:
    content: str = ""
    reasoning_content: str = ""
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ToolRequest:
    tools: tuple[dict[str, Any], ...]
    tool_choice: ToolChoice | None
    stream: bool


def capabilities_from_client(client: AsyncLLMClient) -> LLMCapabilities:
    capabilities = getattr(client, "capabilities", None)
    return capabilities if isinstance(capabilities, LLMCapabilities) else DEFAULT_LLM_CAPABILITIES


def resolve_tool_request(
    tool_definitions: list[dict[str, Any]],
    tool_choice: ToolChoice,
    *,
    stream: bool,
    capabilities: LLMCapabilities,
) -> ToolRequest:
    """Resolve provider-safe tool parameters for one completion request."""
    if tool_choice == "none" or not tool_definitions or not capabilities.native_tool_calling:
        return ToolRequest(tools=(), tool_choice=None, stream=stream)

    effective_choice: ToolChoice = tool_choice
    if tool_choice == "required" and not capabilities.supports_tool_choice_required:
        effective_choice = "auto"
    effective_stream = stream and capabilities.streaming_tool_calls
    return ToolRequest(
        tools=tuple(tool_definitions),
        tool_choice=effective_choice,
        stream=effective_stream,
    )


def normalize_tool_arguments(arguments: Any) -> str:
    """Normalize SDK/provider argument values to the canonical JSON string form."""
    if isinstance(arguments, str):
        return arguments
    if arguments is None:
        return "{}"
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))


def _value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalize_tool_call(tool_call: Any, index: int) -> ToolCallInfo:
    function = _value(tool_call, "function")
    return ToolCallInfo(
        id=str(_value(tool_call, "id") or f"call_{index}"),
        type="function",
        function=ToolCallFunction(
            name=str(_value(function, "name") or ""),
            arguments=normalize_tool_arguments(_value(function, "arguments")),
        ),
    )


def normalize_chat_completion(response: Any) -> LLMTurn:
    """Convert an OpenAI SDK/LiteLLM completion into the canonical agent turn."""
    choice = _value(response, "choices")[0]
    message = _value(choice, "message")
    raw_tool_calls = _value(message, "tool_calls", None) or []
    return LLMTurn(
        content=extract_message_text(_value(message, "content", "")),
        reasoning_content=extract_message_text(_value(message, "reasoning_content", "")),
        tool_calls=tuple(_normalize_tool_call(tool_call, index) for index, tool_call in enumerate(raw_tool_calls)),
        finish_reason=_value(choice, "finish_reason"),
    )


@dataclass(slots=True)
class _StreamingToolCall:
    id: str = ""
    name: str = ""
    argument_parts: list[Any] = field(default_factory=list)


class ChatCompletionStreamNormalizer:
    """Incrementally normalize OpenAI/LiteLLM stream chunks into one turn."""

    def __init__(self) -> None:
        self._content_parts: list[str] = []
        self._reasoning_parts: list[str] = []
        self._finish_reason: str | None = None
        self._tool_calls: dict[int, _StreamingToolCall] = {}

    def add(self, chunk: Any) -> LLMStreamDelta:
        choices = _value(chunk, "choices", None) or []
        if not choices:
            return LLMStreamDelta()
        choice = choices[0]
        finish_reason = _value(choice, "finish_reason")
        if finish_reason is not None:
            self._finish_reason = str(finish_reason)
        delta = _value(choice, "delta")
        content = extract_message_text(_value(delta, "content", ""))
        reasoning_content = extract_message_text(_value(delta, "reasoning_content", ""))
        if content:
            self._content_parts.append(content)
        if reasoning_content:
            self._reasoning_parts.append(reasoning_content)

        for position, raw_tool_call in enumerate(_value(delta, "tool_calls", None) or []):
            raw_index = _value(raw_tool_call, "index", position)
            index = int(raw_index if raw_index is not None else position)
            accumulated = self._tool_calls.setdefault(index, _StreamingToolCall())
            call_id = _value(raw_tool_call, "id")
            if call_id:
                accumulated.id = str(call_id)
            function = _value(raw_tool_call, "function")
            if function is not None:
                name = _value(function, "name")
                if name:
                    accumulated.name = str(name)
                arguments = _value(function, "arguments")
                if arguments is not None:
                    accumulated.argument_parts.append(arguments)
        return LLMStreamDelta(
            content=content,
            reasoning_content=reasoning_content,
            finish_reason=self._finish_reason,
        )

    def finish(self) -> LLMTurn:
        tool_calls = []
        for index, call in sorted(self._tool_calls.items()):
            if all(isinstance(part, str) for part in call.argument_parts):
                arguments: Any = "".join(call.argument_parts)
            elif len(call.argument_parts) == 1:
                arguments = call.argument_parts[0]
            else:
                arguments = call.argument_parts
            tool_calls.append(
                ToolCallInfo(
                    id=call.id or f"call_{index}",
                    type="function",
                    function=ToolCallFunction(
                        name=call.name,
                        arguments=normalize_tool_arguments(arguments),
                    ),
                )
            )
        return LLMTurn(
            content="".join(self._content_parts),
            reasoning_content="".join(self._reasoning_parts),
            tool_calls=tuple(tool_calls),
            finish_reason=self._finish_reason,
        )
