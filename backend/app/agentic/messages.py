from __future__ import annotations

from datetime import datetime

from app.agentic.protocol import AgentMessage
from app.agentic.runtime.timezones import SHANGHAI_TIMEZONE

DEFAULT_HISTORY_CHARACTERS = 40_000
_MAX_HISTORY_CHARACTERS = DEFAULT_HISTORY_CHARACTERS
_MAX_HISTORY_USER_CHARACTERS = 10_000
_RUNTIME_DATE_SECTION = "## 运行时日期与时间"


def _runtime_date_context(current_time: datetime | None = None) -> str:
    """生成供模型解释相对日期的上海时区运行时上下文。"""
    if current_time is None:
        shanghai_time = datetime.now(SHANGHAI_TIMEZONE)
    elif current_time.tzinfo is None:
        shanghai_time = current_time.replace(tzinfo=SHANGHAI_TIMEZONE)
    else:
        shanghai_time = current_time.astimezone(SHANGHAI_TIMEZONE)

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


def _history_character_budget(context_length_tokens: int, max_characters: int = _MAX_HISTORY_CHARACTERS) -> int:
    """按模型上下文长度推导历史上限字符数；0 表示未设置，沿用配置上限。

    中文场景按 1 字符 ≈ 1 token 保守估计；为 system prompt、当前消息与
    补全预留约 6k tokens。``max_characters`` 是历史预算上限（可配置），
    小上下文模型仍然只能拿到较小值。
    """
    ceiling = max(4_000, int(max_characters))
    if context_length_tokens <= 0:
        return ceiling
    return min(ceiling, max(4_000, context_length_tokens - 6_000))


def _compact_history(
    history: list[AgentMessage] | None,
    current_message: str,
    max_history_messages: int,
    context_length_tokens: int = 0,
    max_history_characters: int = _MAX_HISTORY_CHARACTERS,
) -> list[dict[str, str]]:
    """只保留完整、可直接回灌模型的用户/助手文本历史。"""
    history_budget = _history_character_budget(context_length_tokens, max_history_characters)
    # 单条上限就是历史预算本身。此前是 ``min(_MAX_HISTORY_CHARACTERS, budget)``，
    # 于是把 ``chat_max_history_characters`` 调大到 200k 对单条长消息完全无效：
    # 用户粘一份长研报，仍然只能带 40k 进去。总量本来就被 history_budget 兜住，
    # 而模型窗口未知时预算就等于运维配置的上限——那是运维的明确意图，不该再砍一刀。
    item_ceiling = history_budget
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
    # 给当前用户消息留余量。固定 10k 在默认 40k 预算下是 1/4；预算调小时如果
    # 仍然固定扣 10k，扣完就没余量了，历史会被静默整段丢掉。
    user_reserve = min(_MAX_HISTORY_USER_CHARACTERS, history_budget // 4)
    for item in reversed(compact):
        if len(selected) >= max_history_messages:
            break
        item_limit = item_ceiling
        if not selected and item["role"] == "assistant":
            # 扣到无余量就停：负 slice 会把助手历史静默变成空串，而 [-0:] 又会取回全文。
            item_limit -= user_reserve
        if item_limit <= 0:
            break
        if len(item["content"]) > item_limit:
            item = {**item, "content": item["content"][-item_limit:]}
        next_total = total_characters + len(item["content"])
        if next_total > history_budget:
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
    context_length_tokens: int = 0,
    max_history_characters: int = _MAX_HISTORY_CHARACTERS,
) -> list[dict]:
    """构造 Agent 执行消息，包含 system prompt、工具规则和截断历史。

    Param:
        message: 用户当前消息
        history: 历史消息列表
        max_history_messages: 最大保留的历史消息条数
        system_prompt: Agent 的 system prompt
        tool_selection_prompt: 工具选择规则
        current_time: 可注入的当前时间，仅用于确定性测试；无时区时按上海时间解释
        context_length_tokens: 模型上下文长度，用于推导历史预算（0=未设置）
        max_history_characters: 历史预算上限（来自配置，默认 40k）
    Return:
        符合 OpenAI 格式的消息字典列表
    """
    # Prompt-prefix caching: static content first, volatile content strictly last.
    # Providers cache the longest common prefix, so putting the per-second runtime
    # clock after the Skill/tool rules keeps the whole static head cacheable across
    # the rounds of one run. Appending the clock first (the old order) invalidated
    # every token after it, including all Skill rules, on every single request.
    content = system_prompt
    if tool_selection_prompt:
        content = content + "\n## 工具选择策略（按优先级）\n\n" + tool_selection_prompt
    if _RUNTIME_DATE_SECTION not in content:
        content = content.rstrip() + "\n\n" + _runtime_date_context(current_time)

    messages: list[dict] = [{"role": "system", "content": content}]

    messages.extend(
        _compact_history(
            history,
            message,
            max_history_messages,
            context_length_tokens,
            max_history_characters,
        )
    )

    messages.append({"role": "user", "content": message})
    return messages
