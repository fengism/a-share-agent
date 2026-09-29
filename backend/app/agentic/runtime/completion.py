"""Shared completion semantics for Agent and synthesis output."""

from __future__ import annotations

from app.agentic.semantics import model_stop_code


def completion_warning(
    finish_reason: str | None,
    *,
    has_tool_calls: bool = False,
) -> str | None:
    code = model_stop_code(finish_reason)
    if code == "stop":
        return None
    if code == "tool_calls" and has_tool_calls:
        return None
    return {
        "length": "模型输出达到长度上限，回答可能不完整",
        "content_filter": "模型内容过滤终止了输出，回答可能不完整",
        "stream_error": "模型流式响应中断，已保留已生成内容",
    }.get(code, "模型输出未正常结束，回答可能不完整")
