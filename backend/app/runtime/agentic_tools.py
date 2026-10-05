"""Bind product use cases to Agent Tool application ports."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from app.agentic.tools.application import (
    ApplicationToolHandlers,
    configure_application_tool_handlers,
)
from app.core.request_context import get_current_user, get_current_user_id
from app.modules.daily_review.public import DailyReviewRequest, generate_daily_review
from app.modules.industry_chain.public import research_industry_chain
from app.modules.market_intelligence.public import analyze_twitter_user
from app.modules.quant.public import (
    QuantStrategyDraftBacktestRequest,
    QuantStrategyDraftGenerateRequest,
    backtest_strategy_draft,
    generate_strategy_draft,
    publish_strategy_draft,
    validate_strategy_draft,
)
from app.modules.quant.schemas import QuantUniverse
from app.modules.screener.public import ScreenerFilter, get_industry_list, screen_stocks
from app.modules.stock_comparison.public import compare_stocks


async def _compare_stocks(codes: list[str] | str) -> Any:
    results = await compare_stocks(codes)
    return {"comparison": [item.model_dump(exclude_none=True) for item in results]}


async def _search_stocks(query: str) -> Any:
    from app.financial_data.stock import public as stock_data

    result = await stock_data.search_stocks(query)
    return [item.model_dump() for item in result]


async def _get_stock_documents(**kwargs: Any) -> Any:
    from app.financial_data.stock import public as stock_data

    return await stock_data.get_stock_documents(**kwargs)


async def _get_stock_info(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_basic_info(code)).model_dump()


async def _get_stock_valuation_detail(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_valuation_detail(code)).model_dump()


async def _get_stock_technical_indicators(code: str, period: str = "daily") -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_technical_indicators(code, period=period)).model_dump(exclude={"series"})


async def _get_stock_kline(code: str, period: str = "daily") -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_kline(code, period=period)).model_dump()


async def _get_stock_financial(code: str, indicator: str = "balance") -> Any:
    from app.financial_data.stock import public as stock_data

    return await stock_data.get_financial(code, indicator=indicator)


async def _get_stock_financial_metrics(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_financial_metrics(code)).model_dump()


async def _get_stock_revenue_breakdown(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_revenue_breakdown(code)).model_dump(mode="json", exclude_none=True)


async def _get_stock_news(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    result = await stock_data.get_stock_news(code)
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in result]


async def _get_stock_sentiment(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_stock_sentiment(code)).model_dump(mode="json")


async def _get_stock_risk_data(code: str) -> Any:
    from app.financial_data.stock import public as stock_data

    return (await stock_data.get_stock_risk_data(code)).model_dump(mode="json")


async def _get_hk_stock_profile(code: str) -> Any:
    from app.financial_data.hk.analysis_support import get_hk_stock_profile

    return await get_hk_stock_profile(code)


async def _get_hk_market_overview() -> Any:
    from app.financial_data.hk.analysis_support import get_hk_market_overview

    return await get_hk_market_overview()


async def _get_market_overview() -> Any:
    from app.financial_data.market import public as market_data

    indices: Any
    volume: Any
    indices, volume = await asyncio.gather(
        market_data.get_indices(),
        market_data.get_market_volume(),
        return_exceptions=True,
    )
    result: dict[str, Any] = {}
    if not isinstance(indices, Exception) and indices is not None:
        result["indices"] = indices.model_dump()
    if not isinstance(volume, Exception) and volume is not None:
        result["volume"] = volume.model_dump(mode="json")
    return result


async def _get_hot_rank(type: str = "stocks") -> Any:
    from app.financial_data.market import public as market_data

    if type == "concepts":
        return await market_data.get_ths_hot_concept()
    if type == "industries":
        return await market_data.get_ths_hot_industry()
    return await market_data.get_hot_stocks()


async def _get_industry_rankings(date: str | None = None) -> Any:
    from datetime import date as parse_date

    from app.financial_data.market import public as market_data

    return await market_data.get_industry_rankings(
        parse_date.fromisoformat(date) if date else None,
    )


async def _get_market_mainline() -> Any:
    from app.financial_data.market import public as market_data

    return (await market_data.get_market_mainline()).model_dump(mode="json")


async def _get_sector_stocks_history(date: str, plate_id: str) -> Any:
    from datetime import date as parse_date

    from app.financial_data.market import public as market_data

    result = await market_data.get_sector_stocks_history(parse_date.fromisoformat(date), plate_id)
    return result.model_dump(mode="json")


async def _get_dragon_tiger(date: str | None = None) -> Any:
    from app.financial_data.market import public as market_data

    return await market_data.get_dragon_tiger_list(date)


async def _get_macro_data() -> Any:
    from app.financial_data.market import public as market_data

    return await market_data.get_macro_data()


async def _iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    from app.financial_data import public as financial_data

    return await financial_data.iwencai_search(query, channel=channel, size=size)


async def _iwencai_query(query: str, limit: int = 30) -> Any:
    from app.financial_data import public as financial_data

    return await financial_data.iwencai_query(query, limit=limit)


async def _iwencai_select_stock(query: str, limit: int = 20) -> Any:
    from app.financial_data import public as financial_data

    return await financial_data.iwencai_select_stock(query, limit=limit)


async def _iwencai_market_macro(query: str, limit: int = 20) -> Any:
    from app.financial_data import public as financial_data

    return await financial_data.iwencai_market_macro(query, limit=limit)


async def _generate_daily_review(date: str | None = None, force: bool = False) -> Any:
    user_id = get_current_user_id()
    if user_id is None:
        raise RuntimeError("当前请求缺少登录用户")
    return await generate_daily_review(
        DailyReviewRequest(date=date or None, force=force),
        user_id,
    )


async def _get_industries() -> Any:
    return await get_industry_list()


async def _research_industry_chain(name: str) -> Any:
    return await research_industry_chain(name)


async def _screen_stocks(**kwargs: Any) -> Any:
    filter_data = {key: value for key, value in kwargs.items() if value is not None}
    filter_data.setdefault("page", 1)
    filter_data.setdefault("page_size", 20)
    result = await screen_stocks(ScreenerFilter(**filter_data))
    return result.model_dump()


async def _analyze_twitter_user(username: str) -> Any:
    return await analyze_twitter_user(username)


def _require_quant_admin_id() -> int:
    user = get_current_user()
    if user is None:
        raise RuntimeError("当前请求缺少登录用户")
    if not bool(user["is_admin"]):
        raise PermissionError("仅管理员可以管理在线量化策略")
    return int(user["id"])


async def _list_quant_dsl_capabilities() -> Any:
    _require_quant_admin_id()
    return {
        "api_version": "quant.strategy/v1",
        "data_fields": ["open", "high", "low", "close", "volume"],
        "indicator_operators": ["sma", "ema", "rsi", "rolling_max", "rolling_min"],
        "signal_operators": [
            "greater_than",
            "greater_or_equal",
            "less_than",
            "less_or_equal",
            "cross_above",
            "cross_below",
            "and",
            "or",
            "not",
        ],
        "position_modes": ["binary"],
        "workflow": ["generate", "validate", "backtest", "publish"],
        "restrictions": [
            "仅支持日线声明式 DSL",
            "禁止任意代码、自定义函数和外部数据源",
            "发布前必须通过当前定义快照的回测质量门禁",
        ],
    }


async def _generate_quant_strategy_draft(prompt: str) -> Any:
    draft = await generate_strategy_draft(
        QuantStrategyDraftGenerateRequest(prompt=prompt),
        user_id=_require_quant_admin_id(),
    )
    return draft.model_dump(mode="json")


async def _validate_quant_strategy_draft(draft_id: str) -> Any:
    _require_quant_admin_id()
    draft = await validate_strategy_draft(draft_id)
    return draft.model_dump(mode="json")


async def _backtest_quant_strategy_draft(
    draft_id: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    benchmark: str = "000300",
    minimum_trade_count: int = 1,
    maximum_drawdown_pct: float = 80,
    minimum_sharpe_ratio: float | None = None,
    minimum_holdout_trade_count: int | None = None,
    maximum_holdout_drawdown_pct: float | None = None,
    minimum_holdout_sharpe_ratio: float | None = None,
) -> Any:
    user_id = _require_quant_admin_id()
    run = await backtest_strategy_draft(
        draft_id,
        QuantStrategyDraftBacktestRequest(
            universe=QuantUniverse(source="custom", codes=codes),
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            benchmark=benchmark,
            minimum_trade_count=minimum_trade_count,
            maximum_drawdown_pct=maximum_drawdown_pct,
            minimum_sharpe_ratio=minimum_sharpe_ratio,
            minimum_holdout_trade_count=minimum_holdout_trade_count,
            maximum_holdout_drawdown_pct=maximum_holdout_drawdown_pct,
            minimum_holdout_sharpe_ratio=minimum_holdout_sharpe_ratio,
        ),
        user_id=user_id,
    )
    return run.model_dump(mode="json")


async def _publish_quant_strategy_draft(
    draft_id: str,
    expected_definition_hash: str,
) -> Any:
    _require_quant_admin_id()
    draft = await publish_strategy_draft(
        draft_id,
        expected_definition_hash=expected_definition_hash,
    )
    return draft.model_dump(mode="json")


def configure_application_tools() -> None:
    configure_application_tool_handlers(
        ApplicationToolHandlers(
            analyze_twitter_user=_analyze_twitter_user,
            backtest_quant_strategy_draft=_backtest_quant_strategy_draft,
            compare_stocks=_compare_stocks,
            generate_daily_review=_generate_daily_review,
            generate_quant_strategy_draft=_generate_quant_strategy_draft,
            get_dragon_tiger=_get_dragon_tiger,
            get_hot_rank=_get_hot_rank,
            get_industries=_get_industries,
            get_macro_data=_get_macro_data,
            get_market_mainline=_get_market_mainline,
            get_market_overview=_get_market_overview,
            get_industry_rankings=_get_industry_rankings,
            get_sector_stocks_history=_get_sector_stocks_history,
            get_stock_financial=_get_stock_financial,
            get_stock_financial_metrics=_get_stock_financial_metrics,
            get_stock_revenue_breakdown=_get_stock_revenue_breakdown,
            get_stock_documents=_get_stock_documents,
            get_stock_info=_get_stock_info,
            get_stock_kline=_get_stock_kline,
            get_stock_news=_get_stock_news,
            get_stock_risk_data=_get_stock_risk_data,
            get_stock_sentiment=_get_stock_sentiment,
            get_stock_technical_indicators=_get_stock_technical_indicators,
            get_stock_valuation_detail=_get_stock_valuation_detail,
            get_hk_stock_profile=_get_hk_stock_profile,
            get_hk_market_overview=_get_hk_market_overview,
            iwencai_market_macro=_iwencai_market_macro,
            iwencai_query=_iwencai_query,
            iwencai_search=_iwencai_search,
            iwencai_select_stock=_iwencai_select_stock,
            list_quant_dsl_capabilities=_list_quant_dsl_capabilities,
            publish_quant_strategy_draft=_publish_quant_strategy_draft,
            research_industry_chain=_research_industry_chain,
            search_stocks=_search_stocks,
            screen_stocks=_screen_stocks,
            validate_quant_strategy_draft=_validate_quant_strategy_draft,
        )
    )


__all__ = ["configure_application_tools"]
