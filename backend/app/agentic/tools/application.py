"""Application-owned Tool handlers injected by the runtime composition layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

AsyncHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ApplicationToolHandlers:
    analyze_twitter_user: AsyncHandler
    compare_stocks: AsyncHandler
    backtest_quant_strategy_draft: AsyncHandler
    generate_daily_review: AsyncHandler
    generate_quant_strategy_draft: AsyncHandler
    get_dragon_tiger: AsyncHandler
    get_hot_rank: AsyncHandler
    get_industries: AsyncHandler
    get_macro_data: AsyncHandler
    get_market_mainline: AsyncHandler
    get_market_overview: AsyncHandler
    get_industry_rankings: AsyncHandler
    get_sector_stocks_history: AsyncHandler
    get_stock_financial: AsyncHandler
    get_stock_financial_metrics: AsyncHandler
    get_stock_revenue_breakdown: AsyncHandler
    get_stock_info: AsyncHandler
    get_stock_kline: AsyncHandler
    get_stock_news: AsyncHandler
    get_stock_risk_data: AsyncHandler
    get_stock_sentiment: AsyncHandler
    get_stock_technical_indicators: AsyncHandler
    get_stock_valuation_detail: AsyncHandler
    iwencai_market_macro: AsyncHandler
    iwencai_query: AsyncHandler
    iwencai_search: AsyncHandler
    iwencai_select_stock: AsyncHandler
    list_quant_dsl_capabilities: AsyncHandler
    publish_quant_strategy_draft: AsyncHandler
    research_industry_chain: AsyncHandler
    search_stocks: AsyncHandler
    screen_stocks: AsyncHandler
    validate_quant_strategy_draft: AsyncHandler


_handlers: ApplicationToolHandlers | None = None


def configure_application_tool_handlers(handlers: ApplicationToolHandlers) -> None:
    global _handlers
    _handlers = handlers


def get_application_tool_handlers() -> ApplicationToolHandlers:
    if _handlers is None:
        raise RuntimeError("Application Tool handlers 尚未配置")
    return _handlers


__all__ = [
    "ApplicationToolHandlers",
    "configure_application_tool_handlers",
    "get_application_tool_handlers",
]
