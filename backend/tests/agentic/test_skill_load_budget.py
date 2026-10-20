"""load_skill uses a separate per-run budget, not the data-tool budget."""

from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.runtime.tool_budget import budget_rejection_message
from app.configuration import get_settings


def _context(limit: int) -> AgentExecutionContext:
    settings = get_settings().model_copy(update={"chat_max_skill_loads_total": limit})
    return AgentExecutionContext(settings=settings)


async def test_skill_load_budget_is_separate_and_refundable():
    context = _context(1)
    data_budget = context.tool_calls_remaining

    token, rejection = await context.reserve_skill_load_with_diagnostics("load_skill")

    assert token is not None
    assert rejection is None
    assert context.skill_loads_remaining == 0
    assert context.tool_calls_remaining == data_budget

    second, rejection = await context.reserve_skill_load_with_diagnostics("load_skill")

    assert second is None
    assert rejection == {"reason": "skill_total", "used": 1, "limit": 1}

    assert await context.settle_tool_reservation(token, shared=True) is True
    assert context.skill_loads_remaining == 1
    assert context.tool_calls_remaining == data_budget


async def test_zero_skill_budget_rejects_without_touching_data_budget():
    context = _context(0)
    data_budget = context.tool_calls_remaining

    token, rejection = await context.reserve_skill_load_with_diagnostics("load_skill")

    assert token is None
    assert rejection == {"reason": "skill_total", "used": 0, "limit": 0}
    assert context.tool_calls_remaining == data_budget


def test_skill_budget_rejection_message():
    message = budget_rejection_message({"reason": "skill_total", "used": 3, "limit": 3})

    assert "Skill 加载额度已用尽" in message
    assert "3/3" in message
