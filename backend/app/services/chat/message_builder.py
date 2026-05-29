from __future__ import annotations

from app.models.chat import ChatMessage
from app.services.chat.prompts import SYSTEM_PROMPT


def build_messages(
    message: str,
    history: list[ChatMessage] | None,
    max_history_messages: int,
) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    recent = history[-max_history_messages:] if history else []
    if recent and recent[-1].role == "user" and (recent[-1].content or "") == message:
        recent = recent[:-1]

    for msg in recent:
        if msg.role == "user":
            messages.append({"role": "user", "content": msg.content or ""})
        elif msg.role == "assistant":
            entry: dict = {"role": "assistant", "content": msg.content}
            if msg.reasoning_content:
                entry["reasoning_content"] = msg.reasoning_content
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(entry)
        elif msg.role == "tool":
            messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content or "",
            })

    messages.append({"role": "user", "content": message})
    return messages
