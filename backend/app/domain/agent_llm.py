"""Provider-neutral LLM tool-calling contracts and normalization.

Lives in the domain layer so the agent runtime can depend on it without
importing infrastructure adapters or provider configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.domain.agent_protocol import ToolCallFunction, ToolCallInfo
from app.domain.llm import DEFAULT_LLM_CAPABILITIES, LLMCapabilities

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


def _normalize_legacy_function_call(function_call: Any) -> ToolCallInfo | None:
    """把 ``message.function_call`` 归一成单元素 tool_calls。

    OpenAI 在 tools 之前用 ``function_call``（流式则是 ``delta.function_call``），
    部分自建/老版本网关至今仍只实现这一种。名称缺失时返回 None，避免驱动一轮
    注定失败的调用。
    """
    if not function_call:
        return None
    name = str(_value(function_call, "name", "") or "").strip()
    if not name:
        return None
    return ToolCallInfo(
        id="call_legacy_0",
        type="function",
        function=ToolCallFunction(
            name=name,
            arguments=normalize_tool_arguments(_value(function_call, "arguments", None)),
        ),
    )


def normalize_tool_arguments(arguments: Any) -> str:
    """Normalize SDK/provider argument values to the canonical JSON string form."""
    if isinstance(arguments, str):
        return arguments
    if arguments is None:
        return "{}"
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))


def extract_message_text(content: Any) -> str:
    """Normalize text and provider-specific content block responses."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


_EMPTY_FINISH_REASONS = frozenset({"", "none", "null"})


def normalize_finish_reason(value: Any) -> str | None:
    """收敛网关对"无结束原因"的不同写法。

    部分 OpenAI 兼容网关（vLLM/llama.cpp 等）在流末尾返回空串或字符串
    ``"null"``。按缺失处理，让上层的"缺失则校验内容完整性"兜底生效，而不是
    直接判成异常中止把已经完整的内容丢掉。统一小写以便与成功集合比较。
    """
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_FINISH_REASONS:
        return None
    return text.lower()


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
    tool_calls = tuple(
        _normalize_tool_call(tool_call, index) for index, tool_call in enumerate(raw_tool_calls)
    )
    if not tool_calls:
        # 老网关只回 legacy 的单次 function_call；丢掉它等于"模型调了工具但什么都没发生"。
        legacy = _normalize_legacy_function_call(_value(message, "function_call", None))
        if legacy is not None:
            tool_calls = (legacy,)
    return LLMTurn(
        content=extract_message_text(_value(message, "content", "")),
        reasoning_content=extract_message_text(_value(message, "reasoning_content", "")),
        tool_calls=tool_calls,
        finish_reason=normalize_finish_reason(_value(choice, "finish_reason")),
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
        finish_reason = normalize_finish_reason(_value(choice, "finish_reason"))
        if finish_reason is not None:
            self._finish_reason = finish_reason
        delta = _value(choice, "delta")
        content = extract_message_text(_value(delta, "content", ""))
        reasoning_content = extract_message_text(_value(delta, "reasoning_content", ""))
        if content:
            self._content_parts.append(content)
        if reasoning_content:
            self._reasoning_parts.append(reasoning_content)

        raw_tool_calls = _value(delta, "tool_calls", None) or []
        if not raw_tool_calls:
            # 老网关流式只发 delta.function_call，且后续分片只带参数片段（没有 name），
            # 因此必须逐片合并字段，不能走"名称缺失即跳过"的整包归一化。
            legacy_delta = _value(delta, "function_call", None)
            if legacy_delta is not None:
                accumulated = self._tool_calls.setdefault(0, _StreamingToolCall())
                legacy_name = str(_value(legacy_delta, "name", "") or "").strip()
                if legacy_name:
                    accumulated.name = legacy_name
                legacy_arguments = _value(legacy_delta, "arguments", None)
                if isinstance(legacy_arguments, str):
                    accumulated.argument_parts.append(legacy_arguments)
                elif legacy_arguments is not None:
                    accumulated.argument_parts.append(
                        json.dumps(legacy_arguments, ensure_ascii=False, separators=(",", ":"))
                    )
        for position, raw_tool_call in enumerate(raw_tool_calls):
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
    "extract_message_text",
    "normalize_chat_completion",
    "normalize_tool_arguments",
    "resolve_tool_request",
]
