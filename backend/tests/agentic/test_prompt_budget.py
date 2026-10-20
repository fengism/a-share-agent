"""Prompt-side budget accounting: history ceiling and total prompt cap.

`chat_max_tool_context_characters` only bounds the tool results. System prompt,
history and the current message are separate accounts, so without a total cap a
long conversation can push the whole prompt far past any single limit.
"""

from __future__ import annotations

from app.agentic.agents.executor import (
    _MIN_TOOL_CONTEXT_CHARACTERS,
    _bound_tool_context_for_prompt_budget,
)
from app.agentic.messages import (
    DEFAULT_HISTORY_CHARACTERS,
    _history_character_budget,
    build_messages,
)
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.configuration import get_settings


def _context(**updates) -> AgentExecutionContext:
    return AgentExecutionContext(settings=get_settings().model_copy(update=updates))


def _history(count: int, characters: int) -> list[AgentMessage]:
    return [
        AgentMessage(role="user" if index % 2 == 0 else "assistant", content=f"{index}" * characters)
        for index in range(count)
    ]


def test_history_budget_respects_configured_ceiling():
    assert _history_character_budget(0) == DEFAULT_HISTORY_CHARACTERS
    assert _history_character_budget(0, 80_000) == 80_000
    # A small context window still wins over a large configured ceiling.
    assert _history_character_budget(20_000, 80_000) == 14_000
    # The configured ceiling wins over a huge context window.
    assert _history_character_budget(400_000, 80_000) == 80_000


def test_larger_history_budget_keeps_more_turns():
    # History must still start with a user turn, so four turns are needed for a
    # difference to be observable.
    history = _history(4, 15_000)

    def retained(ceiling: int) -> int:
        messages = build_messages(
            "现在的问题",
            history,
            max_history_messages=10,
            system_prompt="system",
            max_history_characters=ceiling,
        )
        return len(messages) - 2  # system + current message

    assert retained(DEFAULT_HISTORY_CHARACTERS) == 2
    assert retained(60_000) == 4


def test_prompt_budget_is_disabled_by_default():
    messages = build_messages("问题", None, 5, system_prompt="system")

    assert _bound_tool_context_for_prompt_budget(messages, 60_000, _context()) == 60_000


def test_prompt_budget_keeps_tool_context_when_under_cap():
    messages = build_messages("问题", None, 5, system_prompt="system")

    bounded = _bound_tool_context_for_prompt_budget(
        messages, 60_000, _context(chat_max_prompt_characters=200_000)
    )

    assert bounded == 60_000


def test_prompt_budget_shrinks_tool_context_to_the_remainder(monkeypatch):
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)

    messages = [{"role": "system", "content": "S" * 25_000}]
    bounded = _bound_tool_context_for_prompt_budget(
        messages, 60_000, _context(chat_max_prompt_characters=30_000)
    )

    assert bounded == 5_000
    events = fresh.snapshot()["agentic"]["events"]
    assert events["agent_prompt_budget_reduced"] == 1
    assert "agent_prompt_budget_exceeded" not in events


def test_prompt_budget_floors_tool_context_at_the_minimum(monkeypatch):
    from app.agentic.agents import executor as executor_module
    from app.core.metrics import MetricsRegistry

    fresh = MetricsRegistry()
    monkeypatch.setattr(executor_module, "metrics", fresh)

    messages = [{"role": "system", "content": "S" * 50_000}]
    bounded = _bound_tool_context_for_prompt_budget(
        messages, 60_000, _context(chat_max_prompt_characters=10_000)
    )

    # The prompt alone already exceeded the cap; tools still get the floor so the
    # model is not left with zero evidence capacity.
    assert bounded == _MIN_TOOL_CONTEXT_CHARACTERS
    events = fresh.snapshot()["agentic"]["events"]
    assert events["agent_prompt_budget_reduced"] == 1
    assert events["agent_prompt_budget_exceeded"] == 1


def test_small_history_ceiling_never_empties_a_turn():
    """调小 chat_max_history_characters 不能把助手历史静默变成空串。

    旧逻辑固定为当前用户消息预留 10k，再对小预算做负 slice：`content[-(-6000):]`
    取到的是空串，而 `content[-0:]` 又会取回全文——两者都是一个静默错误。
    """
    history = [
        AgentMessage(role="user", content="U" * 3_000),
        AgentMessage(role="assistant", content="A" * 3_000),
    ]

    for ceiling in (4_000, 8_000, 12_000, 40_000):
        messages = build_messages(
            "现在的问题",
            history,
            max_history_messages=10,
            system_prompt="system",
            max_history_characters=ceiling,
        )
        kept = messages[1:-1]
        assert all(item["content"] for item in kept), ceiling
        if kept:
            assert kept[0]["role"] == "user"
        assert sum(len(item["content"]) for item in kept) <= ceiling


def test_prompt_cap_also_bounds_the_orchestration_dependency_context():
    """chat_max_prompt_characters 必须同样压住编排层的依赖上下文。"""
    from app.agentic.orchestration.executor import (
        _MAX_DEPENDENCY_CONTEXT_CHARACTERS,
        _MIN_DEPENDENCY_CONTEXT_CHARACTERS,
        _prompt_budget_for_dependencies,
    )

    # 未启用时不改变既有行为。
    assert (
        _prompt_budget_for_dependencies(_context()) == _MAX_DEPENDENCY_CONTEXT_CHARACTERS
    )
    # 上限很宽时也不提前收紧。
    assert (
        _prompt_budget_for_dependencies(_context(chat_max_prompt_characters=1_000_000))
        == _MAX_DEPENDENCY_CONTEXT_CHARACTERS
    )
    # 上限很紧时收缩到剩余量，但不低于下限。
    bounded = _prompt_budget_for_dependencies(_context(chat_max_prompt_characters=40_000))
    assert _MIN_DEPENDENCY_CONTEXT_CHARACTERS <= bounded < _MAX_DEPENDENCY_CONTEXT_CHARACTERS
    assert bounded == 16_000
    assert (
        _prompt_budget_for_dependencies(_context(chat_max_prompt_characters=8_000))
        == _MIN_DEPENDENCY_CONTEXT_CHARACTERS
    )


def test_a_single_long_message_may_use_the_whole_raised_budget():
    """调大 chat_max_history_characters 必须对单条长消息也生效。

    此前单条被 `_MAX_HISTORY_CHARACTERS`(40k) 硬顶，运维把预算调到 200k 也没用：
    用户粘一份长研报仍然只能带 40k 进去。
    """
    long_turn = "报" * 90_000  # AgentMessage 协议上限是 100k
    history = [
        AgentMessage(role="user", content=long_turn),
        AgentMessage(role="assistant", content="已读"),
    ]

    messages = build_messages(
        "现在的问题",
        history,
        max_history_messages=10,
        system_prompt="system",
        max_history_characters=200_000,
    )

    retained = [message for message in messages if message["role"] != "system"][:-1]
    assert retained, "长消息应当被保留"
    assert sum(len(message["content"]) for message in retained) > 60_000
    # 总量仍然受预算约束。
    assert sum(len(message["content"]) for message in retained) <= 200_000


def test_default_budget_still_caps_a_single_message_at_40k():
    long_turn = "报" * 90_000  # AgentMessage 协议上限是 100k
    messages = build_messages(
        "现在的问题",
        [AgentMessage(role="user", content=long_turn), AgentMessage(role="assistant", content="已读")],
        max_history_messages=10,
        system_prompt="system",
    )
    retained = [message for message in messages if message["role"] != "system"][:-1]
    assert sum(len(message["content"]) for message in retained) <= 40_000
