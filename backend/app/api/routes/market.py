"""市场 API 聚合路由。"""

from fastapi import APIRouter

from app.api.routes.market_sections import concept, intelligence, macro, quotes

router = APIRouter()
router.include_router(quotes.router)
router.include_router(intelligence.router)
router.include_router(concept.router)
macro_router = macro.router

__all__ = ["macro_router", "router"]
