"""Screener 模块对 HTTP 和其他业务适配器开放的稳定入口。"""

from app.financial_data.stock.public import compute_percentiles, get_industry_list
from app.modules.screener.presets import list_screener_presets
from app.modules.screener.schemas import (
    ScreenerFilter,
    ScreenerPreset,
    ScreenerResult,
    ScreenerStrategyMatch,
    ScreenerStrategyParameter,
    ScreenerStrategyPreset,
    ScreenerStrategyRequest,
    ScreenerStrategyResult,
    ValuationPercentileRequest,
    ValuationPercentileResult,
)
from app.modules.screener.screening import screen_stocks
from app.modules.screener.strategy_screening import (
    list_screener_strategies,
    screen_candidates_by_strategy,
    validate_screener_strategy_request,
)

__all__ = [
    "ScreenerFilter",
    "ScreenerPreset",
    "ScreenerResult",
    "ScreenerStrategyMatch",
    "ScreenerStrategyParameter",
    "ScreenerStrategyPreset",
    "ScreenerStrategyRequest",
    "ScreenerStrategyResult",
    "ValuationPercentileRequest",
    "ValuationPercentileResult",
    "compute_percentiles",
    "get_industry_list",
    "list_screener_presets",
    "list_screener_strategies",
    "screen_candidates_by_strategy",
    "screen_stocks",
    "validate_screener_strategy_request",
]
