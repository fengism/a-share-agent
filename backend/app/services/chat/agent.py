from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from app.config import get_settings
from app.models.chat import ChatMessage, ChatStreamDelta, ToolCallFunction, ToolCallInfo
from app.services.chat.message_builder import build_messages
from app.services.chat.tools.registry import registry
from app.services.chat.skills import register_all_skills
from app.services.chat.tool_call_parser import extract_pseudo_tool_calls
from app.services.llm.client import create_openai_chat_runtime

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 5
_MAX_HISTORY_MESSAGES = 20


async def _execute_tool_calls_ordered(tool_calls: list[ToolCallInfo]):
    """并行执行一组工具调用。

    Param:
        tool_calls: 工具调用信息列表
    Return:
        每个工具调用的结果列表，顺序与输入一致
    """
    return await asyncio.gather(*(registry.execute_tool(tc) for tc in tool_calls))


def _build_create_kwargs(model: str, messages: list[dict], tool_choice: str) -> dict:
    """构造调用 LLM chat.completions.create 所需的参数字典。

    Param:
        model: 模型名称
        messages: 消息历史列表
        tool_choice: 工具选择策略（none/auto/required）
    Return:
        包含 model、messages、tools、tool_choice、stream 的参数字典
    """
    return {
        "model": model,
        "messages": messages,
        "tools": registry.get_tool_definitions(),
        "tool_choice": tool_choice,
        "stream": True,
    }


def _build_assistant_tool_message(tool_calls: list[ToolCallInfo], content: str | None = None, reasoning_content: str = "") -> dict:
    """构造包含工具调用的 assistant 消息字典。

    Param:
        tool_calls: 工具调用信息列表
        content: 文本内容，可选
        reasoning_content: 推理内容（如 DeepSeek thinking），可选
    Return:
        符合 OpenAI 格式的 assistant 消息字典
    """
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
    """将流式累积的工具调用字典转换为 ToolCallInfo 列表。

    Param:
        tool_calls_acc: 按 index 索引累积的工具调用数据字典
    Return:
        按 index 排序后的 ToolCallInfo 列表
    """
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
    """聊天 Agent 入口：根据配置分派到多 Agent 编排器或传统单 Agent 循环。

    Param:
        message: 用户当前消息
        history: 历史消息列表，可选
    Return:
        产生 ChatStreamDelta 事件的异步生成器
    """
    register_all_skills()
    settings = get_settings()
    if settings.multi_agent_enabled:
        from app.services.chat.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        async for delta in orchestrator.run(message, history):
            yield delta
    else:
        async for delta in _run_legacy_agent(message, history):
            yield delta


async def _run_legacy_agent(
    message: str,
    history: list[ChatMessage] | None = None,
) -> AsyncGenerator[ChatStreamDelta, None]:
    """传统单 Agent 循环：多轮调用 LLM 并执行工具调用，流式返回增量结果。

    Param:
        message: 用户当前消息
        history: 历史消息列表，可选
    Return:
        产生 ChatStreamDelta 事件的异步生成器，类型包括 text/reasoning/tool_call/tool_result/error/done
    """
    runtime = create_openai_chat_runtime(get_settings())
    client = runtime.client
    model = runtime.model

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
