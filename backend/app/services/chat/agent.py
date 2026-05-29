from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from openai import OpenAI

from app.config import PROVIDER_DEFAULTS, get_settings
from app.models.chat import ChatMessage, ChatStreamDelta, ToolCallFunction, ToolCallInfo
from app.services.chat.message_builder import build_messages
from app.services.chat.skills import registry, register_all_skills
from app.services.chat.tool_call_parser import extract_pseudo_tool_calls

# 启动时注册所有技能
register_all_skills()

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 5
_MAX_HISTORY_MESSAGES = 20


async def _execute_tool_calls_ordered(tool_calls: list[ToolCallInfo]):
    return await asyncio.gather(*(registry.execute(tc) for tc in tool_calls))


def _build_create_kwargs(model: str, messages: list[dict], tool_choice: str) -> dict:
    return {
        "model": model,
        "messages": messages,
        "tools": registry.get_tool_definitions(),
        "tool_choice": tool_choice,
        "stream": True,
    }


def _build_assistant_tool_message(tool_calls: list[ToolCallInfo], content: str | None = None, reasoning_content: str = "") -> dict:
    message = {
        "role": "assistant",
        "content": content or None,
        "tool_calls": [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ],
    }
    if reasoning_content:
        message["reasoning_content"] = reasoning_content
    return message


def _to_tool_call_infos(tool_calls_acc: dict[int, dict]) -> list[ToolCallInfo]:
    return [
        ToolCallInfo(
            id=tc_data["id"],
            type="function",
            function=ToolCallFunction(
                name=tc_data["name"],
                arguments=tc_data["arguments"],
            ),
        )
        for _, tc_data in sorted(tool_calls_acc.items())
    ]


async def run_chat_agent(
    message: str,
    history: list[ChatMessage] | None = None,
) -> AsyncGenerator[ChatStreamDelta, None]:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    base_url = settings.llm_base_url or defaults.get("base_url", "https://api.openai.com/v1")
    model = settings.llm_model or defaults.get("model", "gpt-4o-mini")

    client = OpenAI(api_key=settings.llm_api_key, base_url=base_url, timeout=120.0)

    messages = build_messages(message, history, _MAX_HISTORY_MESSAGES)

    for round_num in range(_MAX_ROUNDS + 1):
        logger.info(f"Agent round {round_num + 1}: calling LLM with {len(messages)} messages")

        if round_num == _MAX_ROUNDS:
            tool_choice = "none"
        else:
            tool_choice = "required" if round_num == 0 else "auto"

        create_kwargs = _build_create_kwargs(model, messages, tool_choice)

        try:
            stream = await asyncio.to_thread(
                client.chat.completions.create,
                **create_kwargs,
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            yield ChatStreamDelta(type="error", error=f"LLM调用失败: {e}")
            return

        assistant_content = ""
        reasoning_content = ""
        tool_calls_acc: dict[int, dict] = {}

        try:
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    assistant_content += delta.content

                # Stream reasoning_content for DeepSeek thinking mode
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    reasoning_content += delta.reasoning_content
                    yield ChatStreamDelta(type="reasoning", content=delta.reasoning_content)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_calls_acc[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_acc[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments
        except Exception as e:
            logger.error(f"Stream processing failed: {e}", exc_info=True)
            yield ChatStreamDelta(type="error", error=f"流式响应处理失败: {e}")
            return

        if not tool_calls_acc:
            # Check for pseudo tool calls in text (some models output tool calls as plain text)
            pseudo_calls = extract_pseudo_tool_calls(assistant_content, registry) if round_num < _MAX_ROUNDS else []
            if pseudo_calls:
                logger.info(
                    f"Round {round_num + 1} detected pseudo tool calls in text: "
                    f"{[pc.function.name for pc in pseudo_calls]}"
                )
                # Replace the streamed text with a tool execution flow
                openai_tool_calls = pseudo_calls
                for tc_info in openai_tool_calls:
                    yield ChatStreamDelta(type="tool_call", tool_call=tc_info)
                messages.append(_build_assistant_tool_message(openai_tool_calls))
                tool_results = await _execute_tool_calls_ordered(openai_tool_calls)
                for tc_info, result in zip(openai_tool_calls, tool_results):
                    logger.info(
                        f"Pseudo tool result: {tc_info.function.name} -> "
                        f"is_error={result.is_error}, content_len={len(result.content)}"
                    )
                    yield ChatStreamDelta(type="tool_result", tool_result=result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.content,
                    })
                continue

            # Final response — include reasoning_content if present for history
            logger.info(
                f"Round {round_num + 1} final response: "
                f"content={assistant_content[:500] if assistant_content else '<empty>'}, "
                f"reasoning={reasoning_content[:200] if reasoning_content else '<none>'}"
            )
            if assistant_content:
                yield ChatStreamDelta(type="text", content=assistant_content)
            if reasoning_content:
                yield ChatStreamDelta(type="done", reasoning_content=reasoning_content)
            break

        openai_tool_calls = _to_tool_call_infos(tool_calls_acc)
        for tc_info in openai_tool_calls:
            yield ChatStreamDelta(type="tool_call", tool_call=tc_info)

        tool_call_summary = ", ".join(
            f"{tc.function.name}({tc.function.arguments[:100]})" for tc in openai_tool_calls
        )
        logger.info(
            f"Round {round_num + 1} tool calls: {tool_call_summary}, "
            f"content={assistant_content[:200] if assistant_content else '<empty>'}, "
            f"tool_choice={tool_choice}"
        )

        messages.append(_build_assistant_tool_message(openai_tool_calls, assistant_content, reasoning_content))

        tool_results = await _execute_tool_calls_ordered(openai_tool_calls)
        for tc_info, result in zip(openai_tool_calls, tool_results):
            logger.info(
                f"Tool result: {tc_info.function.name} -> "
                f"is_error={result.is_error}, "
                f"content_len={len(result.content)}"
            )
            yield ChatStreamDelta(type="tool_result", tool_result=result)
            messages.append({
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": result.content,
            })

    yield ChatStreamDelta(type="done")
