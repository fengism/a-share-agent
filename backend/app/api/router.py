from __future__ import annotations

from typing import Any

from fastapi import APIRouter

import app.modules.portfolio.router as portfolio
import app.modules.quant.router as quant
import app.modules.screener.router as screener
from app.api.errors import OPENAPI_ERROR_RESPONSES
from app.modules.analysis import page_router as analysis_page
from app.modules.analysis import router as analysis
from app.modules.auth import router as auth
from app.modules.bot import admin_router as bot_admin
from app.modules.bot import router as bot
from app.modules.chat import router as chat
from app.modules.daily_review import router as daily_review
from app.modules.industry_chain import router as industry_chain
from app.modules.market import router as market
from app.modules.push import router as push
from app.modules.settings import router as config
from app.modules.stock import router as stock

_PROTECTED_ROUTERS = (
    (stock.router, "/stock", ["stock"]),
    (market.router, "/market", ["market"]),
    (portfolio.router, "/portfolio", ["portfolio"]),
    (quant.router, "/quant", ["quant"]),
    (analysis.router, "/analysis", ["analysis"]),
    (screener.router, "/screener", ["screener"]),
    (daily_review.router, "/daily-review", ["daily-review"]),
    (push.router, "/push", ["push"]),
    (chat.router, "/chat", ["chat"]),
    (config.router, "/config", ["config"]),
    (industry_chain.router, "/industry-chain", ["industry-chain"]),
    (market.macro_router, "/macro", ["macro"]),
    (analysis_page.router, "/stock", ["stock"]),
    (bot_admin.router, "/bot", ["bot-admin"]),
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
