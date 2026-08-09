"""Bind product use cases to Agent Tool application ports."""

from __future__ import annotations

from typing import Any

from app.agentic.tools.application import (
    ApplicationToolHandlers,
    configure_application_tool_handlers,
)
from app.core.request_context import get_current_user_id
from app.modules.daily_review.public import DailyReviewRequest, generate_daily_review
from app.modules.industry_chain.public import research_industry_chain
from app.modules.market.public import analyze_twitter_user
from app.modules.screener.public import ScreenerFilter, get_industry_list, screen_stocks
from app.modules.stock.public import compare_stocks


async def _compare_stocks(codes: list[str] | str) -> Any:
    results = await compare_stocks(codes)
    return {"comparison": [item.model_dump(exclude_none=True) for item in results]}


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


def configure_application_tools() -> None:
    configure_application_tool_handlers(
        ApplicationToolHandlers(
            compare_stocks=_compare_stocks,
            generate_daily_review=_generate_daily_review,
            get_industries=_get_industries,
            research_industry_chain=_research_industry_chain,
            screen_stocks=_screen_stocks,
            analyze_twitter_user=_analyze_twitter_user,
        )
    )


__all__ = ["configure_application_tools"]
