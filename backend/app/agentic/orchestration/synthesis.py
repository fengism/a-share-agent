from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Mapping

from openai import AsyncOpenAI

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.runtime.llm import stream_chat_completion
from app.core.errors import log_internal_error

logger = logging.getLogger(__name__)


async def stream_synthesis(
    message: str,
    results: Mapping[str, AgentExecutionResult],
    llm_client: AsyncOpenAI,
    model: str,
    *,
    system_prompt: str,
    temperature: float = 0.1,
) -> AsyncGenerator[str, None]:
    parts = [f"## {result.display_name}\n{result.analysis}" for result in results.values()]
    synthesis_input = f"用户问题: {message}\n\n" + "\n\n".join(parts)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": synthesis_input},
    ]
    try:
        stream = stream_chat_completion(
            llm_client,
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as exc:
        _, detail = log_internal_error(
            logger,
            "Agentic synthesis",
            exc,
            "综合分析生成失败",
        )
        yield f"\n{detail}\n"
        for result in results.values():
            yield f"\n### {result.display_name}\n{result.analysis}\n"
