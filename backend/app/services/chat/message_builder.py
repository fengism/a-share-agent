from __future__ import annotations

from app.models.chat import ChatMessage
from app.services.chat.prompts import SYSTEM_PROMPT
from app.services.chat.tools.registry import registry


def build_messages(
    message: str,
    history: list[ChatMessage] | None,
    max_history_messages: int,
    system_prompt: str | None = None,
) -> list[dict]:
    """构造发送给 LLM 的消息列表，包含 system prompt、技能指令、截断后的历史和当前用户消息。

    Param:
        message: 用户当前消息
        history: 历史消息列表
        max_history_messages: 最大保留的历史消息条数
        system_prompt: 自定义 system prompt，为 None 时使用默认 SYSTEM_PROMPT + 技能指令
    Return:
        符合 OpenAI 格式的消息字典列表
    """
    content = system_prompt or SYSTEM_PROMPT
    # 自动注入 Skill 自然语言指令（仅使用默认 prompt 时）
    if not system_prompt:
        skill_text = registry.get_skill_prompt()
        if skill_text:
            content = content + "\n## 工具选择策略\n\n" + skill_text

    messages: list[dict] = [{"role": "system", "content": content}]

    recent = history[-max_history_messages:] if history else []
    if recent and recent[-1].role == "user" and (recent[-1].content or "") == message:
        recent = recent[:-1]

    for msg in recent:
        if msg.role == "user":
            messages.append({"role": "user", "content": msg.content or ""})
        elif msg.role == "assistant":
            entry: dict = {"role": "assistant", "content": msg.content}
            # reasoning_content 仅用于前端展示，不回灌 API（部分 provider 如 DeepSeek 会报 400）
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
