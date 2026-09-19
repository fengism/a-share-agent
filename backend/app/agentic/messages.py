from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.agentic.protocol import AgentMessage

_MAX_HISTORY_CHARACTERS = 40_000
_MAX_HISTORY_USER_CHARACTERS = 10_000
_RUNTIME_DATE_SECTION = "## 运行时日期与时间"
_SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _runtime_date_context(current_time: datetime | None = None) -> str:
    """生成供模型解释相对日期的上海时区运行时上下文。"""
    if current_time is None:
        shanghai_time = datetime.now(_SHANGHAI_TIMEZONE)
    elif current_time.tzinfo is None:
        shanghai_time = current_time.replace(tzinfo=_SHANGHAI_TIMEZONE)
    else:
        shanghai_time = current_time.astimezone(_SHANGHAI_TIMEZONE)

    formatted_time = shanghai_time.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{_RUNTIME_DATE_SECTION}\n"
        f"- 当前时间（Asia/Shanghai）：{formatted_time}\n"
        "- ‘今天’‘今日’‘当前’‘今年’等相对时间都以此时间为准。\n"
        "- 用户未指定绝对日期且工具支持默认当天时，调用支持默认当天的工具时省略日期参数，"
        "不要猜测日期。\n"
        "- 工具结果中的数据日期才是实际报告或行情日期；它可能与请求日期不同，"
        "尤其需要区分非交易日的请求日期与最近交易日的数据日期。"
    )


def _compact_history(
    history: list[AgentMessage] | None,
    current_message: str,
    max_history_messages: int,
) -> list[dict[str, str]]:
    """只保留完整、可直接回灌模型的用户/助手文本历史。"""
    compact: list[dict[str, str]] = []
    for item in history or []:
        if item.role not in ("user", "assistant"):
            continue
        content = (item.content or "").strip()
        if not content:
            continue
        compact.append({"role": item.role, "content": content})

    if compact and compact[-1]["role"] == "user" and compact[-1]["content"] == current_message:
        compact.pop()

    selected: list[dict[str, str]] = []
    total_characters = 0
    for item in reversed(compact):
        if len(selected) >= max_history_messages:
            break
        item_limit = _MAX_HISTORY_CHARACTERS
        if not selected and item["role"] == "assistant":
            item_limit -= _MAX_HISTORY_USER_CHARACTERS
        if len(item["content"]) > item_limit:
            item = {**item, "content": item["content"][-item_limit:]}
        next_total = total_characters + len(item["content"])
        if next_total > _MAX_HISTORY_CHARACTERS:
            break
        selected.append(item)
        total_characters = next_total
    selected.reverse()

    while selected and selected[0]["role"] != "user":
        selected.pop(0)
    return selected


def build_messages(
    message: str,
    history: list[AgentMessage] | None,
    max_history_messages: int,
    system_prompt: str,
    tool_selection_prompt: str = "",
    *,
    current_time: datetime | None = None,
) -> list[dict]:
    """构造 Agent 执行消息，包含 system prompt、工具规则和截断历史。

    Param:
        message: 用户当前消息
        history: 历史消息列表
        max_history_messages: 最大保留的历史消息条数
        system_prompt: Agent 的 system prompt
        tool_selection_prompt: 工具选择规则
        current_time: 可注入的当前时间，仅用于确定性测试；无时区时按上海时间解释
    Return:
        符合 OpenAI 格式的消息字典列表
    """
    content = system_prompt
    if _RUNTIME_DATE_SECTION not in content:
        content = content.rstrip() + "\n\n" + _runtime_date_context(current_time)
    if tool_selection_prompt:
        content = content + "\n## 工具选择策略（按优先级）\n\n" + tool_selection_prompt

    messages: list[dict] = [{"role": "system", "content": content}]

    messages.extend(_compact_history(history, message, max_history_messages))

    messages.append({"role": "user", "content": message})
    return messages
