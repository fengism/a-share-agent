"""Request-local industry research budgets; never mutate global chat settings."""

from app.configuration import get_effective_settings

BODY_TOOLS = ("web_fetch", "fetch_urls", "read_pdf")
# One shared discovery group: switching search backends must not reset its allowance.
SEARCH_TOOLS = ("web_search", "iwencai_search", "iwencai_query", "iwencai_select_stock")


def search_policy_limits(total: int, *, repair: bool = False) -> dict:
    limit = min(8 if repair else 24, max(1, total // 3))
    return {
        "search_tool_names": SEARCH_TOOLS,
        "search_total_limit": limit,
        "search_burst_limit": min(2 if repair else 4, limit),
    }


def research_budget_settings(settings=None, *, repair: bool = False, overrides: dict | None = None):
    settings = settings if settings is not None else get_effective_settings()
    key = "industry_chain_repair_tool_calls_total" if repair else "industry_chain_tool_calls_total"
    total = int(getattr(settings, key))
    return settings.model_copy(update={**(overrides or {}), "chat_max_tool_calls_total": total}), total
