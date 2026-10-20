"""首轮工具集的顺序与体积。

两个缺陷是连在一起的：

1. ``_selected_skills`` 无视调用方顺序，一律按注册顺序重排。capability_plan 传来的
   顺序是**相关度顺序**，于是查新闻时 ``web_search`` 被排到 ``web_fetch``/``fetch_urls``
   之后（那两个来自得分最低的 Skill）。
2. 只要再加上「首轮工具数上限」，按错误顺序截断就会先把 ``web_search`` 截掉——
   上限机制本身会把缺陷放大成事故。
"""

from __future__ import annotations

import json

import pytest

from app.agentic.catalog import registry
from app.agentic_integration.bootstrap import register_all_capabilities
from app.modules.chat.capability_plan import build_chat_capability_plan


def _plan(message: str, *, cap: int = 0, max_skills: int = 3):
    register_all_capabilities()
    return build_chat_capability_plan(
        message,
        max_initial_active_skills=max_skills,
        core_tools_enabled=True,
        max_initial_tools=cap,
    )


def _schema_characters(names) -> int:
    total = 0
    for name in names:
        tool = registry.get_tool(name)
        assert tool is not None, name
        total += len(json.dumps(
            {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
            ensure_ascii=False,
        ))
    return total


# --- 顺序 ------------------------------------------------------------------


def test_tools_follow_skill_relevance_order():
    plan = _plan("搜索一下光伏行业新闻")

    assert plan.initial_skill_names[0] == "information_query"
    assert plan.tool_names[0] == "web_search", (
        f"得分最高的 Skill 的主工具必须排第一，实际顺序：{list(plan.tool_names)}"
    )
    # url_content 的正文工具属于最低分 Skill，不该挤到搜索工具前面。
    assert list(plan.tool_names).index("web_search") < list(plan.tool_names).index("web_fetch")


def test_selected_skills_respect_a_sequence_but_stay_deterministic_for_sets():
    from app.agentic.catalog import registry as catalog

    ordered = [skill.name for skill in catalog._selected_skills(("market_data", "stock_analysis"))]
    assert ordered == ["market_data", "stock_analysis"]

    # 集合没有顺序可言：退回注册顺序，保证 prompt 前缀稳定。
    from_set = [skill.name for skill in catalog._selected_skills({"market_data", "stock_analysis"})]
    assert from_set == [
        name for name in (skill.name for skill in catalog.list_skills())
        if name in {"market_data", "stock_analysis"}
    ]


# --- 上限 ------------------------------------------------------------------


def test_cap_zero_keeps_every_core_tool():
    plan = _plan("分析茅台估值", cap=0)
    assert len(plan.tool_names) > 8
    assert "search_stocks" in plan.tool_names


def test_cap_truncates_but_keeps_the_most_relevant_tools():
    uncapped = _plan("分析茅台估值", cap=0)
    capped = _plan("分析茅台估值", cap=6)

    assert list(capped.tool_names) == list(uncapped.tool_names)[:6]
    assert capped.tool_names[0] == "search_stocks"
    assert _schema_characters(capped.tool_names) < _schema_characters(uncapped.tool_names) / 2


def test_cap_larger_than_available_is_a_no_op():
    uncapped = _plan("分析茅台估值", cap=0)
    generous = _plan("分析茅台估值", cap=64)
    assert generous.tool_names == uncapped.tool_names


def test_capped_tools_stay_loadable_through_the_skill():
    """被截掉的工具不是消失：active_tool_names 仍然包含它们（load_skill 靠这个扩展）。"""
    plan = _plan("分析茅台估值", cap=4)

    assert len(plan.tool_names) == 4
    assert set(plan.tool_names) < set(plan.active_tool_names)


def test_cap_never_touches_load_skill():
    """load_skill 由宿主在 core tools 之后追加，不能被上限截掉。"""
    plan = _plan("分析茅台估值", cap=1)
    assert len(plan.tool_names) == 1
    assert "load_skill" not in plan.tool_names  # 不在 core tools 里
    assert registry.get_tool("load_skill") is not None  # 但它确实存在


# --- stream() 参数对齐 ------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_forwards_the_same_knobs_as_run(monkeypatch):
    """stream() 少一个参数，流式调用方就会静默失去对应保证。"""
    from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
    from app.agentic.agents.executor import AgentExecutor

    captured: dict = {}

    async def fake_run(self, profile, message, history, llm_client, model, **kwargs):
        captured.update(kwargs)
        return AgentExecutionResult(
            agent_name=profile.name, display_name=profile.display_name, analysis="结论",
        )

    monkeypatch.setattr(AgentExecutor, "run", fake_run)
    cache = object()
    events = []

    async def drain():
        async for event in AgentExecutor().stream(
            AgentProfile(
                name="s-agent", display_name="S", description="d",
                system_prompt="s", tool_names=(),
            ),
            "问题",
            None,
            object(),
            "m",
            tool_call_reserve=2,
            task_id="step-1",
            attempt=3,
            tool_cache=cache,  # type: ignore[arg-type]
        ):
            events.append(event)

    await drain()

    assert captured["tool_call_reserve"] == 2
    assert captured["task_id"] == "step-1"
    assert captured["attempt"] == 3
    assert captured["tool_cache"] is cache
    assert captured["stream_response"] is True
    assert events[-1].type == "done"
