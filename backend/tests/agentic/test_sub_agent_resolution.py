"""Profession sub-agents must be able to resolve an ambiguous target.

Two defects were found together:

1. Every stock-domain profile injects the ``stock_analysis`` Skill rules, and those
   rules say "仅有名称或代码不完整时先调用一次 search_stocks" — but no profile
   actually had ``search_stocks``. The model was told to call a tool it did not have.
2. Layer C (unresolved target) only reached the general agent. On the orchestrated
   path the flag was merely counted, so a keyword-routed news/fundamental task got
   no instruction at all.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.executor import stream_execution_plan
from app.agentic_integration.agents.catalog import list_agent_profiles
from app.agentic_integration.bootstrap import register_all_capabilities
from app.modules.chat.stock_reference import RESOLVER_TOOL_NAME


def _profiles() -> list[AgentProfile]:
    register_all_capabilities()
    return list(list_agent_profiles())


def test_every_stock_domain_profile_can_resolve_a_target():
    offenders = [
        profile.name
        for profile in _profiles()
        if "stock_analysis" in tuple(getattr(profile, "skill_names", ()) or ())
        and RESOLVER_TOOL_NAME not in profile.tool_names
    ]
    assert not offenders, (
        "这些 Agent 注入了 stock_analysis 规则（要求先调用 search_stocks 消歧）"
        f"但工具清单里没有 {RESOLVER_TOOL_NAME}: {offenders}"
    )


def test_market_level_agent_is_not_forced_to_resolve_a_target():
    """宏观 Agent 不针对个股，给它消歧工具只增加选择面。"""
    macro = next(profile for profile in _profiles() if profile.name == "macro")
    assert RESOLVER_TOOL_NAME not in macro.tool_names
    assert "stock_analysis" not in tuple(getattr(macro, "skill_names", ()) or ())


class _CapturingExecutor:
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    async def run(self, profile: AgentProfile, message: str, *args: Any, **kwargs: Any):
        self.prompts[profile.name] = kwargs.get("tool_selection_prompt", "")
        return AgentExecutionResult(
            agent_name=profile.name,
            status="succeeded",
            content=f"{profile.name} ok",
        )


async def _run_plan(instruction):
    from app.agentic.orchestration import executor as executor_module

    capturing = _CapturingExecutor()
    original = executor_module.agent_executor
    executor_module.agent_executor = capturing
    try:
        profiles = {
            profile.name: profile
            for profile in (
                AgentProfile(
                    name="news",
                    display_name="新闻",
                    description="news",
                    system_prompt="news",
                    tool_names=(RESOLVER_TOOL_NAME, "get_stock_news"),
                    max_rounds=1,
                ),
                AgentProfile(
                    name="macro",
                    display_name="宏观",
                    description="macro",
                    system_prompt="macro",
                    tool_names=("get_industry_overview",),
                    max_rounds=1,
                ),
            )
        }
        plan = ExecutionPlan(
            tasks=[
                AgentTask(
                    task_id="news",
                    agent_name="news",
                    display_name="新闻",
                    objective="新闻",
                    allowed_tools=profiles["news"].tool_names,
                ),
                AgentTask(
                    task_id="macro",
                    agent_name="macro",
                    display_name="宏观",
                    objective="宏观",
                    allowed_tools=profiles["macro"].tool_names,
                ),
            ],
            reuse_task_ids=[],
            reasoning="test",
        )
        events = [
            event
            async for event in stream_execution_plan(
                profiles,
                plan,
                "这只票的消息面怎么样",
                None,
                llm_client=None,  # type: ignore[arg-type]
                model="test",
                results={},
                task_instruction=instruction,
            )
        ]
        assert events
    finally:
        executor_module.agent_executor = original
    return capturing.prompts


@pytest.mark.asyncio
async def test_instruction_reaches_only_tasks_that_can_resolve():
    from app.modules.chat.general_agent import STOCK_RESOLUTION_INSTRUCTION

    prompts = await _run_plan(
        lambda task: (
            STOCK_RESOLUTION_INSTRUCTION if RESOLVER_TOOL_NAME in task.allowed_tools else ""
        )
    )
    assert STOCK_RESOLUTION_INSTRUCTION in prompts["news"]
    assert STOCK_RESOLUTION_INSTRUCTION not in prompts["macro"]


@pytest.mark.asyncio
async def test_no_instruction_by_default():
    prompts = await _run_plan(None)
    assert STOCK_RESOLUTION_INSTRUCTION_MARKER not in prompts["news"]


STOCK_RESOLUTION_INSTRUCTION_MARKER = "search_stocks 用用户提到的名称确认代码"


def test_orchestrator_directive_is_scoped_by_the_profile_tool_list():
    """真实策略（而非测试里的 lambda）也必须按 allowed_tools 投递。"""
    from app.modules.chat.general_agent import STOCK_RESOLUTION_INSTRUCTION
    from app.modules.chat.orchestrator import Orchestrator

    def task(tools: tuple[str, ...]) -> AgentTask:
        return AgentTask(
            task_id="t",
            agent_name="news",
            display_name="新闻",
            objective="新闻",
            allowed_tools=tools,
        )

    keyword_off = Orchestrator(needs_stock_resolution=False)._task_instruction(task((RESOLVER_TOOL_NAME,)))
    assert keyword_off == ""

    orchestrator = Orchestrator(needs_stock_resolution=True)
    assert orchestrator._task_instruction(task((RESOLVER_TOOL_NAME,))) == STOCK_RESOLUTION_INSTRUCTION
    assert orchestrator._task_instruction(task(("get_industry_overview",))) == ""
