from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.errors import OPENAPI_ERROR_RESPONSES
from app.api.routes import (
    analysis,
    analysis_page,
    auth,
    bot,
    bot_admin,
    chat,
    daily_review,
    industry_chain,
    portfolio,
    push,
    quant,
    screener,
    watchlist,
    workflows,
)
from app.api.routes import market as market_routes
from app.api.routes import settings as config
from app.api.routes import stock as stock_routes

_PROTECTED_ROUTERS = (
    (stock_routes.router, "/stock", ["stock"]),
    (market_routes.router, "/market", ["market"]),
    (portfolio.router, "/portfolio", ["portfolio"]),
    (watchlist.router, "/watchlist", ["watchlist"]),
    (quant.router, "/quant", ["quant"]),
    (analysis.router, "/analysis", ["analysis"]),
    (screener.router, "/screener", ["screener"]),
    (daily_review.router, "/daily-review", ["daily-review"]),
    (push.router, "/push", ["push"]),
    (chat.router, "/chat", ["chat"]),
    (config.router, "/config", ["config"]),
    (industry_chain.router, "/industry-chain", ["industry-chain"]),
    (market_routes.macro_router, "/macro", ["macro"]),
    (analysis_page.router, "/stock", ["stock"]),
    (bot_admin.router, "/bot", ["bot-admin"]),
    (workflows.router, "/workflows", ["workflows"]),
)


def create_api_router(*, active_user_dependencies: list[Any]) -> APIRouter:
    api_router = APIRouter(prefix="/api", responses=OPENAPI_ERROR_RESPONSES)
    protected_router = APIRouter(dependencies=active_user_dependencies)

    for router, prefix, tags in _PROTECTED_ROUTERS:
        protected_router.include_router(router, prefix=prefix, tags=tags)

    api_router.include_router(protected_router)
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
    api_router.include_router(bot.router, prefix="/bot", tags=["bot"])
    return api_router
