from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.models.chat import ChatMessage, ChatStreamDelta, ToolCallFunction, ToolCallInfo
from app.services.chat.message_builder import build_messages
from app.services.chat.tools.registry import registry

logger = logging.getLogger(__name__)


@dataclass
class SubAgentResult:
    agent_name: str
    display_name: str
    analysis: str
    tools_called: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


class SubAgent:
    def __init__(self, name: str, display_name: str, system_prompt: str,
                 skill_names: list[str], max_rounds: int = 3):
        self.name = name
        self.display_name = display_name
        self.system_prompt = system_prompt
        self.skill_names = skill_names
        self.max_rounds = max_rounds

    async def run(self, message: str, history: list[ChatMessage] | None,
                  llm_client: AsyncOpenAI, model: str,
                  event_queue: asyncio.Queue | None = None) -> SubAgentResult:
        """运行子 Agent：多轮工具调用后生成最终分析。

        Param:
            message: 用户消息
            history: 历史消息列表，可选
            llm_client: 异步 OpenAI 客户端
            model: 模型名称
            event_queue: 可选事件队列，用于实时推送工具调用/结果增量
        Return:
            SubAgentResult，包含最终分析文本、调用过的工具和耗时
        """
        start = time.monotonic()
        messages = build_messages(message, history, 10, system_prompt=self.system_prompt)
        tool_defs = registry.get_tool_definitions_for(self.skill_names)
        tools_called: list[str] = []
        errors: list[str] = []

        async def emit(delta: ChatStreamDelta) -> None:
            """向事件队列推送一条增量（队列为空时静默忽略）。"""
            if event_queue is not None:
                await event_queue.put(delta)

        for round_num in range(self.max_rounds):
            try:
                response = await llm_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    tool_choice="required" if round_num == 0 else "auto",
                    stream=False,
                )
            except Exception as e:
                logger.error(f"SubAgent {self.name} LLM call failed: {e}")
                errors.append(f"LLM调用失败: {e}")
                break

            msg = response.choices[0].message

            if not msg.tool_calls:
                return SubAgentResult(
                    agent_name=self.name,
                    display_name=self.display_name,
                    analysis=msg.content or "",
                    tools_called=tools_called,
                    errors=errors,
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

            assistant_msg = {"role": "assistant", "content": msg.content, "tool_calls": []}
            for tc in msg.tool_calls:
                assistant_msg["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            messages.append(assistant_msg)

            for tc in msg.tool_calls:
                tc_info = ToolCallInfo(
                    id=tc.id,
                    type="function",
                    function=ToolCallFunction(name=tc.function.name, arguments=tc.function.arguments),
                )
                tools_called.append(tc.function.name)
                await emit(ChatStreamDelta(type="tool_call", tool_call=tc_info))
                result = await registry.execute_tool(tc_info)
                await emit(ChatStreamDelta(type="tool_result", tool_result=result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": result.tool_call_id,
                    "content": result.content,
                })
                if result.is_error:
                    errors.append(f"{tc.function.name}: {result.content}")
                logger.info(f"SubAgent {self.name} tool: {tc.function.name}, error={result.is_error}")

        try:
            response = await llm_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[],
                stream=False,
            )
            analysis = response.choices[0].message.content or ""
        except Exception as e:
            analysis = f"最终分析生成失败: {e}"
            errors.append(analysis)

        return SubAgentResult(
            agent_name=self.name,
            display_name=self.display_name,
            analysis=analysis,
            tools_called=tools_called,
            errors=errors,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
