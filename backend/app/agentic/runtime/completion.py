"""Shared completion semantics for Agent and synthesis output."""
from __future__ import annotations


def completion_warning(
    finish_reason: str | None, *, has_tool_calls: bool = False,
) -> str | None:
    if finish_reason in {None, "stop"}:
        return None
    if finish_reason == "tool_calls" and has_tool_calls:
        return None
    return {
        "length": "模型输出达到长度上限，回答可能不完整",
        "content_filter": "模型内容过滤终止了输出，回答可能不完整",
        "stream_error": "模型流式响应中断，已保留已生成内容",
    }.get(finish_reason, "模型输出未正常结束，回答可能不完整")
